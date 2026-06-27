from django.shortcuts import render

from .models import SiteAssets, MushroomType


def index(request):
    start_banner = SiteAssets.objects.get(note="start_banner", is_active=True)
    advantages = SiteAssets.objects.filter(note="advantages", is_active=True)
    shrooms_types = MushroomType.objects.all()

    context = {
        "start_banner": start_banner,
        "advantages": advantages,
        "shrooms_types": shrooms_types,
    }

    return render(request, "shop/index.html", context)
