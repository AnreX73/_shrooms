from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.sitemaps import Sitemap
from django.db.models import Q
from django.urls import reverse

from blog.models import Post
from shop.models import Category, Product


class SiteSitemap(Sitemap):
    """Базовый sitemap: домен и протокол берём из SITE_URL."""

    def get_domain(self, site=None):
        return urlsplit(settings.SITE_URL).netloc

    def get_protocol(self, protocol=None):
        return urlsplit(settings.SITE_URL).scheme or "https"


class StaticSitemap(SiteSitemap):
    changefreq = "weekly"

    def items(self):
        return ["shop:index", "shop:catalog", "shop:info_page"]

    def location(self, item):
        return reverse(item)

    def priority(self, item):
        return {
            "shop:index": 1.0,
            "shop:catalog": 0.9,
            "shop:info_page": 0.3,
        }.get(item, 0.5)


class CategorySitemap(SiteSitemap):
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        return Category.objects.filter(is_active=True)

    def location(self, obj):
        return obj.get_absolute_url()

    def lastmod(self, obj):
        return obj.updated_at


class ProductSitemap(SiteSitemap):
    changefreq = "daily"
    priority = 0.7

    def items(self):
        return Product.objects.filter(
            Q(stock__gt=0) | Q(out_of_stock_behavior="show"),
            category__is_active=True,
        )

    def location(self, obj):
        return obj.get_absolute_url()

    def lastmod(self, obj):
        return obj.updated_at


class BlogSitemap(SiteSitemap):
    changefreq = "monthly"
    priority = 0.6

    def items(self):
        return Post.objects.filter(is_published=True).order_by("-published_at")

    def location(self, obj):
        return reverse("blog:blog_page", args=[obj.slug])

    def lastmod(self, obj):
        return obj.published_at or obj.created_at


sitemaps = {
    "static": StaticSitemap,
    "categories": CategorySitemap,
    "products": ProductSitemap,
    "blog": BlogSitemap,
}
