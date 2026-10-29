import os
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from decouple import Csv, config

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config("SECRET_KEY")

# SECURITY WARNING: don't run with debug turned on in production!
# DEBUG = False


# ALLOWED_HOSTS = ['thirstily-attractive-bird.cloudpub.ru', 'localhost', '127.0.0.1']
DEBUG = config("DEBUG", default=True, cast=bool)

ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="").split(",")

INTERNAL_IPS = [
    # ...
    "127.0.0.1",
    # ...
]


# Application definition

INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
    "chat.apps.ChatConfig",
    "users.apps.UsersConfig",
    "shop.apps.ShopConfig",
    "payments.apps.PaymentsConfig",
    "dashboard.apps.DashboardConfig",
    "blog.apps.BlogConfig",
    "django_extensions",
    "django_q",
    "debug_toolbar",
    "notifications.apps.NotificationsConfig",
    "django_cleanup.apps.CleanupConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "debug_toolbar.middleware.DebugToolbarMiddleware",
]

ROOT_URLCONF = "shroom_shop.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "shroom_shop.context_processors.get_logo",
                "shroom_shop.context_processors.site_settings",
                "shop.context_processors.cart_context",
            ],
        },
    },
]

WSGI_APPLICATION = "shroom_shop.wsgi.application"
ASGI_APPLICATION = "shroom_shop.asgi.application"


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.sqlite3',
#         'NAME': BASE_DIR / 'db.sqlite3',
#     }
# }
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("DB_NAME"),
        "USER": config("DB_USER"),
        "PASSWORD": config("DB_PASSWORD"),
        "HOST": config("DB_HOST"),
        "PORT": config("DB_PORT"),
    }
}


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = "ru"

TIME_ZONE = "Asia/Novosibirsk"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = "/static/"
# Папка, где лежат ваши исходные файлы (JS, CSS, картинки)
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, "static"),
]

# Единая папка для СБОРА всей статики (вашей + админки)
# В разработке она не используется, а в Docker/на сервере — обязательна.
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")


MEDIA_ROOT = os.path.join(BASE_DIR, "media")
MEDIA_URL = "/media/"

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- SEO ---
# Боевой адрес сайта. Используется в canonical, Open Graph, sitemap и robots.txt.
SITE_URL = config("SITE_URL", default="http://localhost:8002").rstrip("/")
SITE_NAME = config("SITE_NAME", default="Лесная фея")
SITE_DESCRIPTION = config(
    "SITE_DESCRIPTION",
    default=(
        "Лесные грибы от «Лесной феи»: сушёные, маринованные и солёные — "
        "натуральный вкус леса с доставкой."
    ),
)

AUTHENTICATION_BACKENDS = [
    "users.authentication.EmailAuthBackend",
    "django.contrib.auth.backends.ModelBackend",
]


AUTH_USER_MODEL = "users.User"
LOGOUT_REDIRECT_URL = "shop:index"

CSRF_TRUSTED_ORIGINS = config(
    "CSRF_TRUSTED_ORIGINS",
    default="http://localhost:8002,http://127.0.0.1:8002",
    cast=Csv(),
)


PASSWORD_HASHERS = [
    "users.hashers.FastPBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",  # для старых паролей
]


REDIS_URL = config("REDIS_URL", default="redis://127.0.0.1:6379/0")

# WebSocket-слой Channels и общий кэш (лимит сообщений в чате) живут в Redis.
# Кэш выносим в соседнюю БД, чтобы не пересекаться с брокером django-q.
_redis_parts = urlsplit(REDIS_URL)
REDIS_CACHE_URL = urlunsplit(
    (_redis_parts.scheme, _redis_parts.netloc, "/1", _redis_parts.query, _redis_parts.fragment)
)

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [REDIS_URL]},
    }
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_CACHE_URL,
    }
}


Q_CLUSTER = {
    "name": "myshop",
    "workers": 2,
    "recycle": 500,
    # Сжатие видео через ffmpeg может идти дольше минуты, поэтому timeout/retry
    # увеличены: retry должен быть больше timeout, иначе задача перезапустится.
    "timeout": 600,
    "retry": 900,
    "max_attempts": 3,  # 0 = бесконечно; ограничиваем перезапуски упавших задач
    "queue_limit": 50,
    "bulk": 10,
    # Брокер Redis. Локально — WSL, в Docker переопределяется на redis://redis:6379/0.
    # Важно: не указывать одновременно "orm", иначе ORM-брокер имеет приоритет.
    "redis": REDIS_URL,
    "save_limit": 1000,
}

RU_EMAIL_PATTERN = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.ru$"

# Дополнительные разрешенные домены, которые не заканчиваются на .ru
EXTRA_ALLOWED_DOMAINS = ["yandex.by", "yandex.kz", "yandex.com"]


# Настройки cookie для CSRF и сессий
CSRF_COOKIE_NAME = "csrftoken_shroomsshop"  # убрать на деплое, хотя это не критично, т.к. CSRF токен генерируется заново при каждой сессии

SESSION_COOKIE_NAME = "sessionid_shroomsshop"  # убрать на деплое, хотя это не критично, т.к. сессия генерируется заново при каждой авторизации

# На проде (DEBUG=False) куки только по HTTPS. В dev сайт открывают по http,
# и Secure-cookie браузер не сохранит — тогда /chat/start/ отдаёт 403.
# Переопределяется переменной COOKIE_SECURE.
COOKIE_SECURE = config("COOKIE_SECURE", default=not DEBUG, cast=bool)
SESSION_COOKIE_SECURE = COOKIE_SECURE
CSRF_COOKIE_SECURE = COOKIE_SECURE
SESSION_COOKIE_HTTPONLY = True  # Куки сессии недоступны через JavaScript

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.mail.ru"

# Используем SSL и порт 465 (рекомендация Mail.ru)
EMAIL_PORT = 465  
EMAIL_USE_SSL = True  
EMAIL_USE_TLS = False  # Обязательно выключаем TLS, они конфликтуют

EMAIL_HOST_USER = "han2201@bk.ru"  
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD")  

# Адрес отправителя по умолчанию
DEFAULT_FROM_EMAIL = "Служба поддержки <han2201@bk.ru>"
SERVER_EMAIL = "han2201@bk.ru"
EMAIL_SUBJECT_PREFIX = "[les-feya.ru] "


DEBUG_TOOLBAR_CONFIG = {
    "DISABLE_PANELS": {
        "debug_toolbar.panels.templates.TemplatesPanel",
    },
}