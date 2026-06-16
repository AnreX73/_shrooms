from django.shortcuts import render

from .models import SiteAssets

def index(request):
    header_image = SiteAssets.objects.get(note="header_image")
    print(header_image)
    context = {
        "header_image": header_image,
    }
    
    return render(request, 'shop/index.html', context)
