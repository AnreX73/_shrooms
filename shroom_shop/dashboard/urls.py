from django.urls import path
from dashboard import views

from dashboard.views import (
    AdminDashboardView,
    ProductCloneView,
    ProductCreateView,
    ProductEditView,
    ProductMediaView,
    ProductSearchView,
    admin_chat_view,
    archived_orders,
    delete_product_media,
    media_item_partial,
    media_status,
    order_archive,
    reorder_product_media,
    request_photo,
    upload_product_media,
  
)

app_name = "dashboard"

urlpatterns = [
    path("admin_area/", AdminDashboardView.as_view(), name="admin_area"),
    path("orders/", views.manage_orders, name="manage_orders"),
    path("orders/<int:order_id>/assign/", views.order_assign, name="order_assign"),
    path(
        "orders/<int:order_id>/processing/",
        views.order_set_processing,
        name="order_processing",
    ),
    path("orders/<int:order_id>/ship/", views.order_ship, name="order_ship"),
    path("orders/<int:order_id>/deliver/", views.order_deliver, name="order_deliver"),
    path("orders/<int:order_id>/cancel/", views.order_cancel, name="order_cancel"),
    # path(
    #     "orders/<int:order_id>/payment-webhook/",
    #     views.order_payment_webhook,
    #     name="order_payment_webhook",
    # ),
    path(
        "orders/items/<int:item_id>/toggle/",
        views.order_item_toggle,
        name="order_item_toggle",
    ),
    path(
        "orders/<int:order_id>/card/",
        views.archive_order_card,
        name="archive_order_card",
    ),
    path("orders/set-manager/", views.set_active_manager, name="set_active_manager"),
    path("orders/<int:order_id>/archive/", order_archive, name="order_archive"),
    path("orders/archived/", archived_orders, name="archived_orders"),
    # ── Товары ──
    path("products/add/", ProductCreateView.as_view(), name="product_create"),
    path("products/<int:pk>/edit/", ProductEditView.as_view(), name="product_edit"),
    path("products/<int:pk>/clone/", ProductCloneView.as_view(), name="product_clone"),
    path("products/search/", ProductSearchView.as_view(), name="product_search"),
    # ── Категории ──
    path("categories/", views.category_list, name="category_list"),
    path("categories/add/", views.category_create, name="category_create"),
    path("categories/<int:pk>/edit/", views.category_edit, name="category_edit"),
    path(
        "categories/<int:pk>/delete/", views.category_delete, name="category_delete"
    ),
    path(
        "categories/<int:pk>/toggle/", views.category_toggle, name="category_toggle"
    ),
    # ── Виды грибов ──
    path("mushroom-types/", views.mushroom_type_list, name="mushroom_type_list"),
    path(
        "mushroom-types/add/",
        views.mushroom_type_create,
        name="mushroom_type_create",
    ),
    path(
        "mushroom-types/<int:pk>/edit/",
        views.mushroom_type_edit,
        name="mushroom_type_edit",
    ),
    path(
        "mushroom-types/<int:pk>/delete/",
        views.mushroom_type_delete,
        name="mushroom_type_delete",
    ),
    path(
        "mushroom-types/<int:pk>/toggle/",
        views.mushroom_type_toggle,
        name="mushroom_type_toggle",
    ),
    # ── AJAX endpoints ──
    path(
        "products/<int:pk>/media/upload/",
        upload_product_media,
        name="upload_product_media",
    ),
    path(
        "products/<int:pk>/media/reorder/",
        reorder_product_media,
        name="reorder_product_media",
    ),
    path("products/<int:pk>/media/", ProductMediaView.as_view(), name="product_media"),
    path(
        "media/<int:media_id>/delete/",
        delete_product_media,
        name="delete_product_media",
    ),
    path("media/<int:media_id>/status/", media_status, name="media_status"),
    path(
        "media/<int:media_id>/partial/", media_item_partial, name="media_item_partial"
    ),
    path("stock-sync/", views.stock_sync, name="stock_sync"),
    path("stock-sync/import/", views.stock_import, name="stock_import"),
    path("stock-sync/export/", views.stock_export, name="stock_export"),
    path("admin-chat/<int:session_id>/", admin_chat_view, name="admin_chat"),
    # Синхронизация цен (новое)
    path("price-sync/", views.price_sync, name="price_sync"),
    path("price-sync/import/", views.price_import, name="price_import"),
    path("price-sync/export/", views.price_export, name="price_export"),
    path(
        "admin-chat/<int:session_id>/request-photo/",
        request_photo,
        name="request_photo",
    ),
    path("chat/", views.chat_list, name="chat_list"),
    path("chat/<int:session_id>/", views.admin_chat, name="admin_chat"),
    path("<int:session_id>/close/", views.close_session, name="chat_close"),
    path("orders/<int:order_id>/note/", views.order_save_note, name="order_save_note"),
    path(
        "orders/<int:order_id>/note/form/",
        views.order_note_form,
        name="order_note_form",
    ),
    path("start-banner/", views.edit_start_banner, name="edit_start_banner"),
]
