
from debug_toolbar.toolbar import debug_toolbar_urls
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth.views import PasswordResetCompleteView, PasswordResetDoneView
from django.urls import include, path
from django.views.generic import TemplateView

from users.views import UserPasswordResetConfirmView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('',include('shop.urls')),
    path("users/", include("users.urls")),
    path(
        "password_reset/done/",
        PasswordResetDoneView.as_view(
            template_name="users/user_password_reset_done.html"
        ),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        UserPasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "reset/done/",
        PasswordResetCompleteView.as_view(
            template_name="users/user_password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),
]+ debug_toolbar_urls()


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)