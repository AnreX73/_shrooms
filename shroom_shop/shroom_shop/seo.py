"""Небольшие помощники для SEO-разметки.

Здесь нет ничего, что требует миграций: все метаданные выводятся из уже
существующих полей моделей.
"""

import json
import re
from urllib.parse import urljoin

from django.conf import settings
from django.utils.html import strip_tags
from django.utils.safestring import mark_safe


def absolute_url(url=""):
    """Возвращает абсолютный URL на основе SITE_URL."""
    if not url:
        return f"{settings.SITE_URL}/"
    if url.startswith(("http://", "https://")):
        return url
    return urljoin(f"{settings.SITE_URL}/", url.lstrip("/"))


def image_url(image):
    """Абсолютный URL изображения или None."""
    if not image:
        return None
    try:
        url = image.url
    except (AttributeError, ValueError):
        return None
    return absolute_url(url)


def make_description(text, fallback="", limit=160):
    """Превращает HTML/текст в аккуратное meta-description."""
    text = strip_tags(text or "")
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        text = (fallback or "").strip()
    if len(text) <= limit:
        return text
    cut = text[: limit - 1]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return f"{cut.rstrip(' ,.;:—-')}…"


def json_ld(data):
    """Безопасная сериализация JSON-LD для вставки в <script>."""
    raw = json.dumps(data, ensure_ascii=False)
    raw = raw.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return mark_safe(raw)
