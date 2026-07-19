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

from .models import Category, Product, SiteAssets, MushroomType, Favorite, Cart,CartItem, Order, Review, ProductImage



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
    start_banner = SiteAssets.objects.filter(note="start_banner", is_active=True).first()
    advantages = SiteAssets.objects.filter(note="advantages", is_active=True)
    shrooms_types = MushroomType.objects.all()
    categories = Category.objects.filter(is_active=True).order_by("created_at")

    context = {
        "start_banner": start_banner,
        "advantages": advantages,
        "shrooms_types": shrooms_types,
        "categories": categories,
    }

    return render(request, "shop/index.html", context)



def catalog(request):
    shrooms_types = MushroomType.objects.all()
    products = Product.objects.all().order_by("-popularity")  # Получаем все продукты
    context = {
        "shrooms_types": shrooms_types,
        "products": products,
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



def product_page(request, slug):
    product = get_object_or_404(
        Product.objects.select_related("category").defer("created_at", "updated_at"),
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