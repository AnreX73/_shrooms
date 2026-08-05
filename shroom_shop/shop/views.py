from django.http import HttpResponse
from django.shortcuts import render
import os

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db import models as db_models
from django.db.models import ExpressionWrapper, F, IntegerField, Max, Min, Prefetch, Q
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST
# from django_q.tasks import async_task

from .models import Category, Info, Product, SiteAssets, MushroomType, Favorite, Cart,CartItem, Order, Review, ProductImage, Contact



def get_hit_ids():
    from django.core.cache import cache

    hit_ids = cache.get("hit_product_ids")
    if hit_ids is None:
        hit_ids = set(
            Product.objects.order_by("-popularity").values_list("id", flat=True)[:24]
        )
        cache.set("hit_product_ids", hit_ids, timeout=3600)
    return hit_ids


def index(request):
    start_banner = Info.objects.filter(name="Стартовый баннер", is_active=True).first()
    advantages = SiteAssets.objects.filter(note="advantages", is_active=True)
    shrooms_types = MushroomType.objects.all()
    categories = Category.objects.filter(is_active=True).order_by("created_at")
    info_objects = Info.objects.all()
    contacts = Contact.objects.all()

    context = {
        "start_banner": start_banner,
        "advantages": advantages,
        "shrooms_types": shrooms_types,
        "categories": categories,
        "info": info_objects,
        "contacts": contacts
    }

    return render(request, "shop/index.html", context)



def catalog(request):
    hit_ids = get_hit_ids()
    products = Product.objects.all().prefetch_related("mushroom_types").order_by("-popularity")  # Получаем все продукты
    context = {
        
        "products": products,
        "hit_ids": hit_ids,
    }
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

            return redirect("payments:create_payment", order_id=order.id)
            # return redirect('shop:order_success', order_id=order.id)

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
    info_items = Info.objects.filter(is_active=True).exclude(name="Стартовый баннер").order_by("created_at")

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


