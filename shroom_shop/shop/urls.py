from django.urls import path


from .views import index, catalog, info_page, toggle_cart, toggle_favorite, product_page, remove_from_cart, update_cart, order_create, order_success

app_name = "shop"

urlpatterns = [
    path("", index, name="index"),
    path("catalog/", catalog, name="catalog"),
    path("toggle_favorite/<int:product_id>/", toggle_favorite, name="toggle_favorite"),
    path("toggle_cart/<int:product_id>/", toggle_cart, name="toggle_cart"),
    path("remove-from-cart/<int:item_id>/", remove_from_cart, name="remove_from_cart"),
    path("update-cart/<int:item_id>/", update_cart, name="update_cart"),
    path(
        "product_page/<slug:slug>/", product_page, name="product_page"
    ),
    path("order-create/", order_create, name="order_create"),
    path("order-success/<int:order_id>/", order_success, name="order_success"),
    path("info/", info_page, name="info_page"),

]
