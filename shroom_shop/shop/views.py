from django.http import HttpResponse
from django.shortcuts import render
import os

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db import models as db_models
from django.db.models import ExpressionWrapper, F, IntegerField, Max, Min, Prefetch, Q
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST
from django_q.tasks import async_task
from django.db.models import (
    Case,
    When,
    Value,
    Count,
    Subquery,
    OuterRef,
)

from django.db.models.functions import Cast
from django.db.models import FloatField


from .forms import ProductFilterForm, OrderForm, ReviewForm
from .models import (
    Product,
    ProductImage,
    Category,
    MushroomType,
    Info,
    SiteAssets,
    Favorite,
    Cart,
    CartItem,
    Order,
    OrderItem,
    Review,
    Contact,
    ReviewMedia,
)
from blog.models import Post, PostBlock


def ru_plural(n, forms):
    """forms = ('товар', 'товара', 'товаров')"""
    n = abs(n) % 100
    n1 = n % 10
    if 10 < n < 20:
        return forms[2]
    if 1 < n1 < 5:
        return forms[1]
    if n1 == 1:
        return forms[0]
    return forms[2]


def get_hit_ids():

    hit_ids = cache.get("hit_product_ids")
    if hit_ids is None:
        hit_ids = set(
            Product.objects.order_by("-popularity").values_list("id", flat=True)[:24]
        )
        cache.set("hit_product_ids", hit_ids, timeout=3600)
    return hit_ids


def index(request):
    first_text_subquery = (
        PostBlock.objects.filter(
            post=OuterRef("pk"),
            block_type="text",
        )
        .order_by("order")
        .values("text")[:1]
    )

    start_banner = Info.objects.filter(name="Стартовый баннер", is_active=True).first()
    advantages = SiteAssets.objects.filter(note="advantages", is_active=True)
    shrooms_types = MushroomType.objects.all()
    categories = Category.objects.filter(is_active=True).order_by("created_at")
    info_objects = (
        Info.objects.all().exclude(name="Стартовый баннер").order_by("created_at")
    )
    contacts = Contact.objects.all()
    main_blog_post = (
        Post.objects.filter(published_on_main_page=True)
        .annotate(first_block_text=Subquery(first_text_subquery))
        .only("title", "slug", "cover_image")
        .first()
    )

    context = {
        "start_banner": start_banner,
        "advantages": advantages,
        "shrooms_types": shrooms_types,
        "categories": categories,
        "info": info_objects,
        "contacts": contacts,
        "main_blog_post": main_blog_post,
    }

    return render(request, "shop/index.html", context)


def _build_remove_url(get_params, key, value=None):
    params = get_params.copy()
    if value is None:
        params.pop(key, None)
    else:
        values = params.getlist(key)
        if value in values:
            values.remove(value)
        if values:
            params.setlist(key, values)
        else:
            params.pop(key, None)
    params.pop("page", None)
    return params.urlencode()


def catalog(request):
    data = request.GET.copy()
    hx_trigger_id = request.headers.get("HX-Trigger", "")
    is_htmx = bool(request.headers.get("HX-Request"))

    # При смене category/mushroom_types сбрасываем ручной price_max —
    # иначе слайдер уедет "выключенным" в новую (возможно более дешёвую) выборку
    if hx_trigger_id in ("category", "mushroom_types"):
        data.pop("price_max", None)

    form = ProductFilterForm(data or None)

    images_prefetch = Prefetch(
        "images",
        queryset=ProductImage.objects.filter(media_type="image").order_by("order"),
        to_attr="prefetched_images",
    )

    products = Product.objects.filter(
        Q(stock__gt=0) | Q(out_of_stock_behavior="show")
    ).annotate(
        computed_final_price=Cast(
            ExpressionWrapper(
                F("price") * (100 - F("discount_percentage")) / 100.0,
                output_field=FloatField(),
            ),
            output_field=IntegerField(),
        )
    )

    selected_category = None
    selected_types = []

    if form.is_valid():
        selected_category = form.cleaned_data.get("category")
        selected_types = list(form.cleaned_data.get("mushroom_types"))

        if selected_category:
            products = products.filter(category=selected_category)

    # --- Границы цены считаем ДО фильтра по price_max, но ПОСЛЕ category/mushroom_types ---
    price_scope = products
    if selected_types:
        price_scope = price_scope.filter(
            mushroom_types__in=[t.pk for t in selected_types]
        ).distinct()

    price_agg = price_scope.aggregate(
        min_price=Min("computed_final_price"),
        max_price=Max("computed_final_price"),
    )
    min_price = price_agg["min_price"] or 0
    max_price = price_agg["max_price"] or 0

    # --- Фильтр: не дороже выбранного значения слайдера ---
    if form.is_valid():
        if (
            pmax := form.cleaned_data.get("price_max")
        ) is not None and pmax < max_price:
            products = products.filter(computed_final_price__lte=pmax)

    # --- Границы веса считаем ДО фильтра по weight_max, но ПОСЛЕ category/mushroom_types ---
    weight_scope = (
        products  # это тот же queryset, что уже прошёл category+mushroom_types,
    )
    # но ДО price_max — если хочешь, чтобы вес не зависел от цены

    weight_agg = weight_scope.aggregate(
        min_weight=Min("net_weight"),
        max_weight=Max("net_weight"),
    )
    min_weight = weight_agg["min_weight"] or 0
    max_weight = weight_agg["max_weight"] or 0

    # --- Фильтр: вес не больше выбранного значения ---
    if form.is_valid():
        if (
            wmax := form.cleaned_data.get("weight_max")
        ) is not None and wmax < max_weight:
            products = products.filter(net_weight__lte=wmax)

    # --- Фильтр + приоритет по видам грибов ---
    if selected_types:
        type_ids = [t.pk for t in selected_types]
        num_selected = len(type_ids)

        # Общее число типов у продукта
        mt_total_sq = (
            Product.objects.filter(pk=OuterRef("pk"))
            .annotate(c=Count("mushroom_types", distinct=True))
            .values("c")[:1]
        )

        # Сколько из ВЫБРАННЫХ типов есть у продукта
        matched_sq = (
            Product.objects.filter(pk=OuterRef("pk"))
            .annotate(
                c=Count(
                    "mushroom_types",
                    filter=Q(mushroom_types__in=type_ids),
                    distinct=True,
                )
            )
            .values("c")[:1]
        )

        products = (
            products.annotate(
                mt_total=Subquery(mt_total_sq, output_field=IntegerField()),
                matched=Subquery(matched_sq, output_field=IntegerField()),
            )
            .filter(mushroom_types__in=type_ids)
            .distinct()
        )

        if num_selected == 1:
            # Один тип: чистый гриб первым, потом наборы
            priority = Case(
                When(mt_total=1, then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            )
            products = products.annotate(priority=priority).order_by(
                "priority", "-popularity", "article"
            )
        else:
            # Несколько типов:
            # 0 — строгое совпадение (только выбранные типы)
            # 1 — нестрогое совпадение (все выбранные + ещё другие)
            # 2 — по отдельности (одиночные грибы)
            # 3 — частичное совпадение (не все выбранные)
            priority = Case(
                When(matched=num_selected, mt_total=num_selected, then=Value(0)),
                When(matched=num_selected, mt_total__gt=num_selected, then=Value(1)),
                When(mt_total=1, then=Value(2)),
                default=Value(3),
                output_field=IntegerField(),
            )
            products = products.annotate(priority=priority).order_by(
                "priority", "-matched", "-popularity", "article"
            )
    else:
        products = products.order_by("-popularity", "article")

    products = products.prefetch_related(images_prefetch)

    # --- Пагинация ---
    filter_keys = {"category", "mushroom_types", "price_max", "weight_max"}
    is_filter_change = (
        any(k in request.GET for k in filter_keys) and "page" not in request.GET
    )

    if is_filter_change:
        page_number = 1
    else:
        page_number = request.GET.get("page", 1)
        request.session["catalog_last_page"] = page_number

    total_matching = products.count()
    paginator = Paginator(products, 12)
    page_obj = paginator.get_page(page_number)

    hit_ids = get_hit_ids()

    # --- Атрибуты слайдера ---
    form.fields["price_max"].widget.attrs["min"] = min_price
    form.fields["price_max"].widget.attrs["max"] = max_price

    current_price_max = (
        form.cleaned_data.get("price_max")
        if form.is_valid() and form.cleaned_data.get("price_max") is not None
        else max_price
    )
    form.fields["price_max"].widget.attrs["value"] = current_price_max

    # Обновляем слайдер через OOB, если запрос пришёл НЕ от самого слайдера
    show_price_oob = hx_trigger_id != "price_max" and is_htmx

    form.fields["weight_max"].widget.attrs["min"] = min_weight
    form.fields["weight_max"].widget.attrs["max"] = max_weight

    current_weight_max = (
        form.cleaned_data.get("weight_max")
        if form.is_valid() and form.cleaned_data.get("weight_max") is not None
        else max_weight
    )
    form.fields["weight_max"].widget.attrs["value"] = current_weight_max

    show_weight_oob = hx_trigger_id != "weight_max" and is_htmx

    # --- Активные фильтры (чипы) ---
    active_filters = []
    if form.is_valid():
        if selected_category:
            active_filters.append(
                {
                    "label": selected_category.name,
                    "remove_url": _build_remove_url(request.GET, "category"),
                }
            )
        for mt in selected_types:
            active_filters.append(
                {
                    "label": mt.name,
                    "remove_url": _build_remove_url(
                        request.GET, "mushroom_types", str(mt.pk)
                    ),
                }
            )
        if current_price_max < max_price:
            active_filters.append(
                {
                    "label": f"до {current_price_max} ₽",
                    "remove_url": _build_remove_url(request.GET, "price_max"),
                }
            )
        if current_weight_max < max_weight:
            active_filters.append(
                {
                    "label": f"вес до {current_weight_max} г",
                    "remove_url": _build_remove_url(request.GET, "weight_max"),
                }
            )

    context = {
        "form": form,
        "page_obj": page_obj,
        "products": page_obj.object_list,
        "hit_ids": hit_ids,
        "min_price": min_price,
        "max_price": max_price,
        "current_price_max": current_price_max,
        "show_price_oob": show_price_oob,
        "current_weight_max": current_weight_max,
        "show_weight_oob": show_weight_oob,
        "active_filters": active_filters,
        "min_weight": min_weight,
        "max_weight": max_weight,
        "total_matching": total_matching,
    }
    context["total_matching_word"] = ru_plural(
        total_matching, ("товар", "товара", "товаров")
    )

    if is_htmx:
        return render(request, "shop/includes/catalog_results.html", context)

    return render(request, "shop/catalog.html", context)


@login_required
@require_POST
def toggle_favorite(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    # Получаем желаемое состояние из Alpine (приходит строкой 'true' или 'false')
    is_favorite_requested = request.POST.get("is_favorite") == "true"

    if is_favorite_requested:
        # Пытаемся создать запись, если её еще нет
        Favorite.objects.get_or_create(user=request.user, product=product)
    else:
        # Удаляем запись, если она существует
        Favorite.objects.filter(user=request.user, product=product).delete()

    return HttpResponse(status=204)  # Успешно, без смены контента


@login_required
@require_POST
def toggle_cart(request, product_id):
    product = Product.objects.get(pk=product_id)
    cart, _ = Cart.objects.get_or_create(user=request.user)

    is_cart = request.POST.get("is_cart") == "true"

    if is_cart:
        CartItem.objects.get_or_create(cart=cart, product=product)
    else:
        CartItem.objects.filter(cart=cart, product=product).delete()

    # Обновляем счётчик в иконке через OOB swap
    cart_count = cart.total_items
    return HttpResponse(
        f'<span id="cart-counter" hx-swap-oob="true" '
        f'x-data="{{ cart_count: {cart_count} }}" '
        f'class="cart_count" x-show="{cart_count} > 0">{cart_count}</span>'
    )


@login_required
def update_cart(request, item_id):
    action = request.POST.get("action")
    cart = request.user.cart
    item = get_object_or_404(CartItem, id=item_id, cart=cart)  # ищем по id CartItem

    if action == "plus":
        item.quantity += 1
    elif action == "minus" and item.quantity > 1:
        item.quantity -= 1

    item.save()

    total = sum(i.total_price for i in cart.items.all())
    context = {
        "user_cart_products": cart.items.select_related("product")
        .prefetch_related(
            Prefetch(
                "product__images",
                queryset=ProductImage.objects.filter(media_type="image").order_by(
                    "order"
                ),
                to_attr="prefetched_images",
            )
        )
        .order_by("-added_at"),
        "user_cart_total": total,
        "user": request.user,
    }
    return render(request, "users/includes/cart_block.html", context)


def remove_from_cart(request, item_id):
    cart, _ = Cart.objects.get_or_create(user=request.user)

    # ищем CartItem напрямую по id
    CartItem.objects.filter(id=item_id, cart=cart).delete()

    user_cart_products = (
        cart.items.select_related("product")
        .prefetch_related(
            Prefetch(
                "product__images",
                queryset=ProductImage.objects.filter(media_type="image").order_by(
                    "order"
                ),
                to_attr="prefetched_images",
            )
        )
        .order_by("-added_at")
    )

    user_cart_total = sum(i.total_price for i in user_cart_products)

    partial = render_to_string(
        "users/includes/cart_block.html",
        {
            "user_cart_products": user_cart_products,
            "user_cart_total": user_cart_total,
        },
        request=request,
    )

    cart_count = cart.total_items
    display = "none" if cart_count == 0 else "flex"

    oob_counter = (
        f'<span id="cart-counter" hx-swap-oob="true" '
        f'class="cart_count" style="display:{display}">'
        f"{cart_count}</span>"
    )

    return HttpResponse(oob_counter + partial)


def product_page(request, slug):
    product = get_object_or_404(
        Product.objects.select_related("category").prefetch_related("mushroom_types"),
        slug=slug,
    )
    product_id = product.id

    product_gallery = ProductImage.objects.filter(product=product).order_by(
        "-created_at"
    )
    video_poster = product_gallery.filter(media_type="image").first()

    images_prefetch = Prefetch(
        "images",
        queryset=ProductImage.objects.filter(media_type="image").order_by("order"),
        to_attr="prefetched_images",
    )
    reviews = Review.objects.filter(product=product, is_approved=True).prefetch_related(
        "media"
    )
    stock_filter = Q(stock__gt=0) | Q(out_of_stock_behavior="show")
    related_products = (
        Product.objects.filter(
            stock_filter,
            category=product.category,
            mushroom_types__in=product.mushroom_types.all(),
        )
        .exclude(id=product_id)
        .select_related("category")
        .prefetch_related(images_prefetch)
    )

    return render(
        request,
        "shop/product_page.html",
        {
            "product": product,
            "product_gallery": product_gallery,
            "video_poster": video_poster,
            "related_products": related_products,
            "reviews": reviews,
            "hit_ids": get_hit_ids(),
        },
    )


@login_required(login_url="/register/")
def order_create(request):
    user = request.user

    try:
        cart = user.cart
        cart_items = cart.items.select_related("product").all()
    except Cart.DoesNotExist:
        return redirect("shop:catalog")

    if not cart_items.exists():
        return redirect("users:profile")

    if request.method == "POST":
        form = OrderForm(user, request.POST)
        if form.is_valid():
            data = form.cleaned_data

            subtotal = cart.total_price
            delivery_cost = 0
            total = subtotal + delivery_cost

            order = Order.objects.create(
                user=user,
                subtotal=subtotal,
                delivery_cost=delivery_cost,
                total=total,
                customer_name=f"{data['first_name']} {data['last_name']}".strip(),
                customer_email=data["customer_email"],
                customer_phone=data["customer_phone"],
                delivery_address=data["delivery_address"],
                delivery_city=data["delivery_city"],
                delivery_postal_code=data["delivery_postal_code"],
                notes=data.get("notes", ""),
            )

            OrderItem.objects.bulk_create(
                [
                    OrderItem(
                        order=order,
                        product=item.product,
                        product_name=item.product.name,
                        product_price=item.product.final_price,
                        quantity=item.quantity,
                    )
                    for item in cart_items
                ]
            )

            for item in cart_items:
                item.product.stock -= item.quantity
                item.product.save(update_fields=["stock"])

            cart_items.delete()

            _update_profile_from_order(user, data)

            # return redirect("payments:create_payment", order_id=order.id)
            return redirect("shop:order_success", order_id=order.id)

    else:
        form = OrderForm(user)

    context = {
        "form": form,
        "cart_items": cart_items,
        "subtotal": cart.total_price,
        "delivery_cost": 0,
        "total": cart.total_price,
    }
    return render(request, "shop/order_create.html", context)


def _update_profile_from_order(user, data):
    user_changed = False
    profile_changed = False

    user_fields = {
        "first_name": data["first_name"],
        "last_name": data["last_name"],
    }
    for attr, value in user_fields.items():
        if value and getattr(user, attr) != value:
            setattr(user, attr, value)
            user_changed = True

    if user_changed:
        user.save(update_fields=list(user_fields.keys()))

    profile_fields = {
        "phone_number": data["customer_phone"],
        "delivery_city": data["delivery_city"],
        "delivery_address": data["delivery_address"],
        "delivery_postal_code": data["delivery_postal_code"],
    }
    for attr, value in profile_fields.items():
        if value and getattr(user, attr, None) != value:
            setattr(user, attr, value)
            profile_changed = True

    if profile_changed:
        user.save(update_fields=list(profile_fields.keys()))


@login_required(login_url="/register/")
def order_success(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, "shop/order_success.html", {"order": order})


def info_page(request):
    # Получаем все активные записи
    info_items = (
        Info.objects.filter(is_active=True)
        .exclude(name="Стартовый баннер")
        .order_by("created_at")
    )

    # Получаем активную вкладку из GET-параметра
    active_tab = request.GET.get("tab", None)

    return render(
        request,
        "shop/info_page.html",
        {
            "info_items": info_items,
            "active_tab": active_tab,
        },
    )


@login_required(login_url="/register/")
def review_create(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    user = request.user

    has_valid_order = Order.objects.filter(
        user=user, status="delivered", payment_status="paid", items__product=product
    ).exists()

    if not has_valid_order:
        messages.error(request, "Вы можете оставить отзыв только на купленный товар.")
        return redirect("users:profile")

    if Review.objects.filter(user=user, product=product).exists():
        messages.info(request, "Вы уже оставляли отзыв на этот товар.")
        return redirect("users:profile")

    if request.method == "POST":
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = Review.objects.create(
                product=product,
                user=user,
                author_name=form.cleaned_data["author_name"],
                rating=form.cleaned_data["rating"],
                title=form.cleaned_data["title"],
                advantages=form.cleaned_data["advantages"],
                disadvantages=form.cleaned_data["disadvantages"],
                text=form.cleaned_data["text"],
                is_approved=True,
            )
            return redirect("shop:review_media", review_id=review.pk)
    else:
        form = ReviewForm()

    return render(
        request,
        "shop/review_create.html",
        {
            "form": form,
            "product": product,
        },
    )


@login_required(login_url="/register/")
def review_media(request, review_id):
    """Шаг 2 — загрузка медиафайлов к отзыву"""
    review = get_object_or_404(
        Review.objects.prefetch_related("media"),
        pk=review_id,
        user=request.user,  # только свой отзыв
    )
    return render(
        request,
        "shop/review_media.html",
        {
            "review": review,
            "product": review.product,
            "max_photos": Review.MAX_PHOTOS,
            "max_videos": Review.MAX_VIDEOS,
        },
    )


@login_required(login_url="/register/")
@require_POST
def upload_review_media(request, review_id):
    """AJAX: загрузка одного файла"""
    review = get_object_or_404(Review, pk=review_id, user=request.user)
    file = request.FILES.get("file")
    if not file:
        return JsonResponse({"error": "Файл не передан"}, status=400)

    ext = os.path.splitext(file.name)[1].lower()
    is_video = ext in {".mp4", ".mov", ".avi", ".webm"}
    media_type = "video" if is_video else "photo"

    # Проверяем лимиты до сохранения
    existing_count = review.media.filter(media_type=media_type).count()
    limit = Review.MAX_VIDEOS if is_video else Review.MAX_PHOTOS
    if existing_count >= limit:
        return JsonResponse(
            {"error": f"Максимум {limit} файлов типа {media_type}"}, status=400
        )

    last_order = (
        review.media.aggregate(max_order=db_models.Max("order"))["max_order"] or 0
    )

    obj = ReviewMedia(
        review=review,
        media_type=media_type,
        file=file,
        order=last_order + 1,
        status="pending",
    )
    obj.save()

    async_task(
        "shop.tasks.compress_review_media",  # поправь путь
        obj.pk,
        task_name=f"compress_review_media_{obj.pk}",
    )

    return JsonResponse(
        {
            "id": obj.pk,
            "media_type": media_type,
            "status": obj.status,
            "preview_url": obj.preview_url,
        }
    )


@login_required(login_url="/register/")
@require_POST
def delete_review_media(request, media_id):
    obj = get_object_or_404(ReviewMedia, pk=media_id, review__user=request.user)
    if obj.file:
        obj.file.delete(save=False)
    if obj.file_compressed:
        obj.file_compressed.delete(save=False)
    obj.delete()
    return JsonResponse({"ok": True})


@login_required(login_url="/register/")
def review_media_status(request, media_id):
    obj = get_object_or_404(ReviewMedia, pk=media_id, review__user=request.user)
    return JsonResponse(
        {
            "status": obj.status,
            "preview_url": obj.preview_url,
        }
    )


@login_required(login_url="/register/")
def review_media_item_partial(request, media_id):
    obj = get_object_or_404(ReviewMedia, pk=media_id, review__user=request.user)
    return render(request, "shop/includes/review_media_item.html", {"media": obj})


def review_popup(request, review_id):
    review = get_object_or_404(Review, id=review_id)
    return render(
        request,
        "shop/includes/review_popup.html",
        {"review": review, "media": review.media.all()},
    )


# ответ на отзыв
@login_required
def add_admin_reply(request, review_id):
    """HTMX-эндпоинт: администратор добавляет ответ на отзыв"""

    # 🔐 Только суперпользователи
    if not request.user.is_superuser:
        return HttpResponseForbidden("Доступ запрещён")

    review = get_object_or_404(
        Review, id=review_id, product_id=request.POST.get("product_id")
    )

    if request.method == "POST":
        answer_text = request.POST.get("answer", "").strip()

        if not answer_text:
            return JsonResponse({"error": "Ответ не может быть пустым"}, status=400)

        # Обновляем только поле ответа
        review.review_answer = answer_text
        review.save(update_fields=["review_answer", "updated_at"])

        # 🔹 Возвращаем готовый HTML-фрагмент для вставки на страницу
        return render(
            request,
            "shop/includes/review_answer_fragment.html",
            {
                "review": review,
                "is_htmx": True,
            },
        )

    return JsonResponse({"error": "Метод не разрешён"}, status=405)


# ===== ЗАГЛУШКА ОПЛАТЫ — УДАЛИТЬ ПОСЛЕ ПОДКЛЮЧЕНИЯ ЭКВАЙРИНГА =====
@login_required(login_url="/register/")
def payment_stub(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    if request.method == "POST":
        order.payment_status = "paid"
        order.status = "pending"
        order.save()
        messages.success(request, "Заказ оплачен  (тестовый режим).")
        return redirect("users:profile")
    return redirect("shop:order_success", order_id=order.id)


# ===== КОНЕЦ ЗАГЛУШКИ =====
