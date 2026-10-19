from django.contrib import admin
from django.utils.safestring import mark_safe

from .models import (
    Cart,
    CartItem,
    Category,
    Contact,
    Favorite,
    Info,
    MushroomType,
    OrderItem,
    Order,
    Product,
    ProductImage,
    SiteAssets,
    Review,
    ReviewMedia,
)


@admin.register(SiteAssets)
class SiteAssetsAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "note", "getHtmlPhoto")
    search_fields = ("name",)
    list_filter = ("is_active",)
    save_on_top = True

    def getHtmlPhoto(self, image):
        if image.image:
            return mark_safe(f"<img src='{image.image.url}' width=50>")

    getHtmlPhoto.short_description = "миниатюра"


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
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
class MushroomTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    list_editable = ("is_active",)
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
class ProductAdmin(admin.ModelAdmin):
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


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ("label", "value", "contact_type", "is_active")
    list_filter = ("contact_type", "is_active")
    search_fields = ("label", "value")
    list_editable = ("is_active",)
    save_on_top = True


@admin.register(Info)
class InfoAdmin(admin.ModelAdmin):
    list_display = ("name", "title", "slug", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "title", "slug")
    list_editable = ("is_active",)
    prepopulated_fields = {"slug": ("name",)}
    save_on_top = True


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ("user", "total_price", "total_items")
    search_fields = ("user",)
    save_on_top = True


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ("cart", "product", "quantity")
    search_fields = ("cart", "product")
    save_on_top = True


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ("user", "product")
    search_fields = ("user", "product")
    save_on_top = True


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("user", "order_number", "status", "payment_status")
    list_editable = ("status", "payment_status")
    search_fields = ("user",)
    save_on_top = True


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("order", "product_name", "quantity", "product_price")
    search_fields = ("order", "product_name")
    save_on_top = True


# отзывы
class ReviewMediaInline(admin.TabularInline):
    model = ReviewMedia
    extra = 0  # Чтобы не плодить пустые поля для новых фото
    readonly_fields = ("preview",)  # Поле только для чтения, где будет картинка

    def preview(self, obj):
        if obj.file:  # Предположим, поле в ReviewMedia называется file
            return mark_safe(f'<img src="{obj.file.url}" style="max-height: 100px;">')
        return "Нет изображения"

    preview.short_description = "Предпросмотр"


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    inlines = [ReviewMediaInline]
    list_display = (
        "product",
        "user",
        "rating",
        "is_approved",
        "get_media_count",
        "created_at",
    )
    list_filter = ("is_approved", "rating", "created_at")
    search_fields = ("title", "text", "user__username", "product__name")
    list_editable = ("is_approved",)
    date_hierarchy = "created_at"
    save_on_top = True

    def get_media_count(self, obj):
        return obj.media.count()

    get_media_count.short_description = "Кол-во медиа"
