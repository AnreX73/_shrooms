from django.urls import path


from .views import index, catalog, toggle_cart, toggle_favorite

app_name = "shop"

urlpatterns = [
    path("", index, name="index"),
    path("catalog/", catalog, name="catalog"),
    path("toggle_favorite/<int:product_id>/", toggle_favorite, name="toggle_favorite"),
    path("toggle_cart/<int:product_id>/", toggle_cart, name="toggle_cart"),

]
