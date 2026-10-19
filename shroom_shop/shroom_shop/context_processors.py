from django.conf import settings
from django.core.cache import cache
from shop.models import SiteAssets


# Разделы, которые не должны попадать в поисковую выдачу.
PRIVATE_URL_PREFIXES = (
    "/admin/",
    "/dashboard/",
    "/users/",
    "/order-create/",
    "/order-success/",
    "/payment-stub/",
    "/review/",
    "/reviews/",
    "/toggle_cart/",
    "/toggle_favorite/",
    "/remove-from-cart/",
    "/update-cart/",
    "/password_reset/",
    "/reset/",
    "/blog/posts/",
    "/blog/post-choice/",
    "/blog/edit/",
    "/blog/blocks/",
    "/blog/images/",
)


def site_settings(request):
    """Общие данные сайта для шаблонов + noindex для служебных страниц."""
    is_private = request.path.startswith(PRIVATE_URL_PREFIXES)
    return {
        "SITE_URL": settings.SITE_URL,
        "SITE_NAME": settings.SITE_NAME,
        "SITE_DESCRIPTION": settings.SITE_DESCRIPTION,
        "seo_robots_default": "noindex, nofollow" if is_private else "index, follow",
    }


def get_logo(request):
    cache_key = "site_assets"
    assets = cache.get(cache_key)

    if not assets:
        try:
            logo = SiteAssets.objects.get(name="logo", is_active=True)
            header_image = SiteAssets.objects.get(name="header_image", is_active=True)
            basket = SiteAssets.objects.get(note="basket", is_active=True)
            assets = {"site_logo": logo, "header_image": header_image, "basket": basket}
            cache.set(cache_key, assets, 3600)
        except SiteAssets.DoesNotExist:
            # Возвращаем значения по умолчанию или пустые значения
            assets = {"site_logo": None, "header_image": None, "basket": None}

    return assets
