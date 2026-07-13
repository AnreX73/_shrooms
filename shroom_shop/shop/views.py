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

from .models import Product, SiteAssets, MushroomType, Favorite, Cart,CartItem, Order, Review


def index(request):
    start_banner = SiteAssets.objects.filter(note="start_banner", is_active=True).first()
    advantages = SiteAssets.objects.filter(note="advantages", is_active=True)
    shrooms_types = MushroomType.objects.all()

    context = {
        "start_banner": start_banner,
        "advantages": advantages,
        "shrooms_types": shrooms_types,
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

