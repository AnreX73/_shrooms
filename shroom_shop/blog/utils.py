def make_slug(text: str, exclude_pk: int | None = None, max_length: int = 200) -> str:
    from .models import Post  # локальный импорт, чтобы избежать циклических импортов

    CHARS = {
        "а": "a",
        "б": "b",
        "в": "v",
        "г": "g",
        "д": "d",
        "е": "e",
        "ё": "yo",
        "ж": "zh",
        "з": "z",
        "и": "i",
        "й": "y",
        "к": "k",
        "л": "l",
        "м": "m",
        "н": "n",
        "о": "o",
        "п": "p",
        "р": "r",
        "с": "s",
        "т": "t",
        "у": "u",
        "ф": "f",
        "х": "h",
        "ц": "ts",
        "ч": "ch",
        "ш": "sh",
        "щ": "sch",
        "ъ": "",
        "ы": "y",
        "ь": "",
        "э": "e",
        "ю": "yu",
        "я": "ya",
    }
    result = "".join(CHARS.get(ch, ch) for ch in text.lower())
    slug = "".join(c if c.isalnum() else "-" for c in result)
    slug = "-".join(part for part in slug.split("-") if part)
    base = slug[:max_length] or "post"

    # проверка уникальности с добавлением суффикса при коллизии
    candidate = base
    counter = 2
    qs = Post.objects.all()
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)

    while qs.filter(slug=candidate).exists():
        suffix = f"-{counter}"
        candidate = f"{base[: max_length - len(suffix)]}{suffix}"
        counter += 1

    return candidate
