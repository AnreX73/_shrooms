from django.contrib import admin

from .models import Post, PostBlock, PostImage


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("title", "is_published", "published_on_main_page", "created_at")
    list_filter = ("is_published", "published_on_main_page", "created_at")
    search_fields = ("title", "excerpt")
    ordering = ("-created_at",)
    prepopulated_fields = {"slug": ("title",)}


class PostImageInline(admin.TabularInline):
    model = PostImage
    extra = 1


@admin.register(PostBlock)
class PostBlockAdmin(admin.ModelAdmin):
    list_display = (
        "post",
        "block_type",
    )
    list_filter = ("block_type", "post")
    search_fields = ("block_type",)
    ordering = ("post", "order")
    inlines = [PostImageInline]
