from django.contrib import admin
from django.db import models
from django.utils.safestring import mark_safe
from unfold.admin import ModelAdmin
from unfold.contrib.forms.widgets import WysiwygWidget

from .models import (
    Category,
    MushroomType,
    Product,
    ProductImage,
    SiteAssets,
)


@admin.register(SiteAssets)
class SiteAssetsAdmin(ModelAdmin):
    list_display = ("name", "is_active", "note", "getHtmlPhoto")
    search_fields = ("name",)
    list_filter = ("is_active",)
    save_on_top = True

    def getHtmlPhoto(self, image):
        if image.image:
            return mark_safe(f"<img src='{image.image.url}' width=50>")

    getHtmlPhoto.short_description = "миниатюра"


@admin.register(Category)
class CategoryAdmin(ModelAdmin):
    formfield_overrides = {
        models.TextField: {
            "widget": WysiwygWidget,
        }
    }
    list_display = ("name", "slug", "getHtmlPhoto", "is_active")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    save_on_top = True
    list_editable = ("is_active",)

    def getHtmlPhoto(self, image):
        if image.image:
            return mark_safe(f"<img src='{image.image.url}' width=50>")

    getHtmlPhoto.short_description = "миниатюра"


@admin.register(MushroomType)
class MushroomTypeAdmin(ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    save_on_top = True


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    readonly_fields = ("get_preview",)
    save_on_top = True

    def get_preview(self, image):
        if image.image:
            return mark_safe(f"<img src='{image.image.url}' width=50>")

    get_preview.short_description = "Превью"


@admin.register(Product)
class ProductAdmin(ModelAdmin):
    formfield_overrides = {
        models.TextField: {
            "widget": WysiwygWidget,
        }
    }
    exclude = ("group_slug",)
    inlines = [ProductImageInline]
    list_display = (
        "name",
        "main_image_preview",
        "stock",
        "article",
        "price",
        "discount_percentage",
        "category",
    )
    list_filter = ("name", "discount_percentage")
    search_fields = ("article", "name", "category__name")
    list_editable = (
        "price",
        "discount_percentage",
    )
    save_on_top = True

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("images")

    def main_image_preview(self, obj):
        main_img = obj.main_image
        if main_img:
            return mark_safe(f'<img src="{main_img.url}" width="50" />')
        return "—"

    main_image_preview.short_description = "Превью"
