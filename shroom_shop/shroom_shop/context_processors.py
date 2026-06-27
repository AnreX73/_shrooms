from django.core.cache import cache
from shop.models import SiteAssets


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
