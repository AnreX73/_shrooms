from django.urls import path

from blog import views

app_name = "blog"

urlpatterns = [
    path("post-choice/", views.post_choice, name="post_choice"),
    path("<slug:slug>/", views.blog_page, name="blog_page"),
    path("posts/new/", views.post_create, name="post_create"),
    path("edit/<int:pk>/", views.post_edit, name="post_edit"),
    path("posts/<int:pk>/delete/", views.post_delete, name="post_delete"),
    path("posts/<int:post_id>/blocks/add/", views.block_add, name="block_add"),
    path(
        "posts/<int:pk>/main-page/confirm/",
        views.main_page_confirm,
        name="main_page_confirm",
    ),
    path(
        "posts/<int:pk>/main-page/toggle/",
        views.main_page_toggle,
        name="main_page_toggle",
    ),
    path("blocks/<int:pk>/update/", views.block_update, name="block_update"),
    path("blocks/<int:pk>/delete/", views.block_delete, name="block_delete"),
    path("blocks/reorder/", views.block_reorder, name="block_reorder"),
    path(
        "blocks/<int:pk>/upload-image/",
        views.upload_gallery_image,
        name="upload_gallery_image",
    ),
    path(
        "blocks/<int:pk>/upload-video/",
        views.upload_short_video,
        name="upload_short_video",
    ),
    path(
        "images/<int:pk>/delete/",
        views.delete_gallery_image,
        name="delete_gallery_image",
    ),
    path(
        "blocks/<int:pk>/video-status/",
        views.block_video_status,
        name="block_video_status",
    ),
    path(
        "blocks/<int:pk>/upload-single-image/",
        views.upload_single_image,
        name="upload_single_image",
    ),
]
