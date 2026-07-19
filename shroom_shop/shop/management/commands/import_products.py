"""
Django management command: импорт товаров (грибы) из Excel-выгрузок Wildberries.

КУДА ПОЛОЖИТЬ ФАЙЛ
-------------------
    <ваше_приложение>/management/commands/import_products.py

Если папок management/commands ещё нет — создайте их и положите пустые __init__.py:
    myapp/management/__init__.py
    myapp/management/commands/__init__.py
    myapp/management/commands/import_products.py   <- этот файл

Замените в начале файла:
    from myapp.models import Product, ProductImage, Category, MushroomType
на реальный путь к вашим моделям.

ЗАПУСК
------
    python manage.py import_products \
        --dried /path/to/dried.xlsx \
        --canned /path/to/canned.xlsx

Можно передать только один из файлов — тогда обработается только он.
Флаг --dry-run считает и печатает, что было бы сделано, ничего не сохраняя в БД.
Флаг --skip-images ускоряет тестовые прогоны (картинки не скачиваются).

КЕШ ИЗОБРАЖЕНИЙ/ВИДЕО
----------------------
По умолчанию скачанные файлы сохраняются в локальный кеш на диске
(--image-cache-dir, по умолчанию ~/.cache/wb_import_images) по ключу —
sha256 от URL. При повторном запуске команды (например, переимпорт после
правки xlsx) файлы с теми же ссылками НЕ скачиваются заново — берутся из
кеша. Это ускоряет повторные прогоны и не грузит внешние серверы лишний
раз. Если нужно принудительно перекачать всё — используйте --no-image-cache.

ЧТО ДЕЛАЕТ КОМАНДА
-------------------
- Читает лист "Items" из каждого xlsx (лист "Manual" — это инструкция WB, игнорируется).
- Ищет категорию по названию:
      dried  -> "Сушёные грибы"
      canned -> "Консервированные грибы"
  (категории должны уже существовать в БД — как у вас и есть).
- update_or_create по полю article (уникальный ключ) — повторный запуск
  безопасно обновит те же товары, а не создаст дубли.
- Разбирает mushroom_types (значения через ";" или ","), сопоставляет с уже
  существующими MushroomType по словарю известных синонимов (белые грибы -> Белый гриб,
  подосиновики -> Подосиновик, и т.д.). Если встречается вид, которого нет в справочнике
  и нет в словаре синонимов (например "маслята" в примере canned-файла), команда
  СОЗДАСТ новый MushroomType с этим названием и выведет предупреждение — проверьте
  такие записи вручную после импорта (могут оказаться опечаткой/дублем).
- Если после разбора у товара получилось больше одного вида грибов —
  автоматически ставит is_set=True (это набор/ассорти). Если ровно один
  вид или ни одного — is_set=False. Проставляется при каждом импорте, т.е.
  переопределяет ручные правки этого поля в админке при повторном запуске
  импорта по тому же article — учитывайте это.
- Парсит "25+ °C" / "+25 °C" / "0 ° C" в обычные целые числа (storage_temp_max/min).
- Парсит "12 мес" / "24" в shelf_life_months (int).
- Скачивает картинки по ссылкам из колонки image (через ";") и создаёт ProductImage
  по порядку (order=0,1,2...). Колонка Video (если есть и не пустая) создаёт
  ProductImage с media_type="video". Скачанные файлы кешируются на диске (см. выше).
- preservation_method и release_form сопоставляются со значениями choices модели
  через словари ниже.

ВАЖНЫЕ ДОПУЩЕНИЯ, КОТОРЫЕ НУЖНО ПРОВЕРИТЬ
-------------------------------------------
1. В обоих xlsx НЕТ колонки с ценой (price). Модель Product.price обязательна
   (default=0), поэтому все импортированные товары получат price=0 —
   ОБЯЗАТЕЛЬНО проставьте цены отдельно (руками/отдельным прайс-листом).
2. В dried-файле нет колонки packaging_height — останется NULL для этих товаров.
3. В canned-файле нет колонки total_weight(kg) — останется NULL для этих товаров.
4. В canned-файле нет колонки is_vegetarian — is_vegetarian останется False
   (значение по умолчанию), хотя по смыслу консервированные грибы тоже
   вегетарианские. Поправьте вручную/добавьте колонку, если это важно.
5. is_gmo_free нигде не задаётся в файлах — всегда False по умолчанию.
6. slug, stock, discount_percentage, out_of_stock_behavior, popularity,
   rating(если пусто), reviews_count — не трогаем, остаются как задано
   моделью (slug сгенерируется автоматически при save()).
7. is_set вычисляется ТОЛЬКО из количества строк mushroom_types в Excel.
   Если у вас есть товары-наборы с одним "сборным" видом гриба (например,
   отдельный MushroomType "Ассорти"), эта эвристика их не распознает —
   их придётся либо завести под отдельным типом с 2+ реальными видами,
   либо проставить is_set вручную после импорта.
"""

import hashlib
import re
import time
import unicodedata
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pandas as pd
import requests
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

# --- ПРАВЬТЕ ЭТОТ ИМПОРТ ПОД СВОЙ ПРОЕКТ ---
from shop.models import Category, MushroomType, Product, ProductImage

# ---------------------------------------------------------------------------
# Словари сопоставления Excel -> choices модели
# ---------------------------------------------------------------------------

PRESERVATION_METHOD_MAP = {
    "сушка": "drying",
    "маринование": "marinating",
    "засолка": "salting",
    "заморозка": "freezing",
}

RELEASE_FORM_MAP = {
    "стеклянная банка": "glass_jar",
    "жестяная банка": "tin_can",
    "пакет": "bag",
    "коробка": "box",
    "вакуумная упаковка": "vacuum",
}

# Известные синонимы названий грибов в Excel -> точное имя MushroomType в БД.
# Ключи — в нижнем регистре, без пробелов по краям.
MUSHROOM_TYPE_SYNONYMS = {
    "белые грибы": "Белый гриб",
    "белый гриб": "Белый гриб",
    "боровики": "Белый гриб",
    "боровик": "Белый гриб",
    "подосиновики": "Подосиновик",
    "подосиновик": "Подосиновик",
    "подберезовики": "Подберезовик",
    "подберёзовики": "Подберезовик",
    "подберезовик": "Подберезовик",
    "подберёзовик": "Подберезовик",
    "опята": "Опята",
    "опята лесные": "Опята",
    "опенок": "Опята",
    "опёнок": "Опята",
    "лисички": "Лисички",
    "лисичка": "Лисички",
    "моховик": "Моховик",
    "моховики": "Моховик",
    "сморчок": "Сморчок",
    "сморчки": "Сморчок",
    "маслята": "Маслёнок",
}

CATEGORY_NAME_DRIED = "Сушёные грибы"
CATEGORY_NAME_CANNED = "Консервированные грибы"

DEFAULT_IMAGE_CACHE_DIR = Path.home() / ".cache" / "wb_import_images"


# ---------------------------------------------------------------------------
# Вспомогательные парсеры
# ---------------------------------------------------------------------------

def clean_str(value):
    """NaN/None -> '' ; иначе строка без лишних пробелов."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return unicodedata.normalize("NFKC", str(value)).strip()


def parse_int(value):
    """Достаёт первое целое число (с учётом знака) из строки типа '25+ °C' / '0 ° C' / '12 мес'."""
    s = clean_str(value)
    if not s:
        return None
    match = re.search(r"-?\d+", s.replace(",", "."))
    if not match:
        return None
    return int(match.group())


def parse_decimal(value, default=None):
    s = clean_str(value)
    if not s:
        return default
    s = s.replace(",", ".")
    match = re.search(r"-?\d+(\.\d+)?", s)
    if not match:
        return default
    try:
        return Decimal(match.group())
    except InvalidOperation:
        return default


def split_multi(value):
    """Разбивает ';' или ',' - разделённый список, убирая пустые элементы."""
    s = clean_str(value)
    if not s:
        return []
    parts = re.split(r"[;,]", s)
    return [p.strip() for p in parts if p.strip()]


def map_choice(value, mapping, field_label, article):
    s = clean_str(value).lower()
    if not s:
        return ""
    if s in mapping:
        return mapping[s]
    print(f"  [!] {article}: неизвестное значение '{value}' для {field_label}, ставлю 'other'")
    return "other"


# ---------------------------------------------------------------------------
# Команда
# ---------------------------------------------------------------------------

class Command(BaseCommand):
    help = "Импорт товаров (грибы) из Excel-выгрузок Wildberries (сушёные / консервированные)."

    def add_arguments(self, parser):
        parser.add_argument("--dried", type=str, help="Путь к xlsx с сушёными грибами")
        parser.add_argument("--canned", type=str, help="Путь к xlsx с консервированными грибами")
        parser.add_argument("--dry-run", action="store_true", help="Ничего не сохранять, только показать план")
        parser.add_argument("--skip-images", action="store_true", help="Не скачивать картинки (быстрее для теста)")
        parser.add_argument(
            "--image-cache-dir",
            type=str,
            default=str(DEFAULT_IMAGE_CACHE_DIR),
            help="Папка для дискового кеша скачанных картинок/видео (по умолчанию: %(default)s)",
        )
        parser.add_argument(
            "--no-image-cache",
            action="store_true",
            help="Отключить кеш и всегда скачивать файлы заново",
        )

    def handle(self, *args, **options):
        dried_path = options.get("dried")
        canned_path = options.get("canned")
        dry_run = options["dry_run"]
        skip_images = options["skip_images"]

        if not dried_path and not canned_path:
            raise CommandError("Укажите хотя бы один из параметров --dried / --canned")

        # Настраиваем дисковый кеш для медиа (None -> кеш выключен)
        self.image_cache_dir = None
        if not skip_images and not dry_run and not options["no_image_cache"]:
            self.image_cache_dir = Path(options["image_cache_dir"])
            self.image_cache_dir.mkdir(parents=True, exist_ok=True)
            self.stdout.write(f"Кеш изображений: {self.image_cache_dir}")

        jobs = []
        if dried_path:
            jobs.append((dried_path, CATEGORY_NAME_DRIED, "dried"))
        if canned_path:
            jobs.append((canned_path, CATEGORY_NAME_CANNED, "canned"))

        total_created = total_updated = total_errors = 0
        total_from_cache = 0
        total_downloaded = 0

        for path, category_name, kind in jobs:
            try:
                category = Category.objects.get(name=category_name)
            except Category.DoesNotExist:
                raise CommandError(
                    f"Категория '{category_name}' не найдена в БД. "
                    f"Создайте её (Category.objects.create(name='{category_name}')) и запустите снова."
                )

            self.stdout.write(self.style.NOTICE(f"\n=== Импорт из {path} (категория: {category_name}) ==="))
            df = pd.read_excel(path, sheet_name="Items")
            df.columns = [str(c).strip() for c in df.columns]  # в файлах встречаются "packaging_length " с пробелом

            for _, row in df.iterrows():
                article = clean_str(row.get("article"))
                if not article:
                    continue  # пустая/служебная строка

                try:
                    created, error = self._import_row(row, category, kind, dry_run, skip_images)
                    if error:
                        total_errors += 1
                    elif created:
                        total_created += 1
                    else:
                        total_updated += 1
                except Exception as exc:  # noqa: BLE001 - хотим продолжить импорт остальных строк
                    total_errors += 1
                    self.stderr.write(self.style.ERROR(f"  [X] {article}: ошибка импорта — {exc}"))

        self.stdout.write(self.style.SUCCESS(
            f"\nГотово. Создано: {total_created}, обновлено: {total_updated}, ошибок: {total_errors}."
            + (" (dry-run, ничего не сохранено)" if dry_run else "")
        ))
        if not dry_run:
            self.stdout.write(self.style.WARNING(
                "\nНапоминание: у импортированных товаров price=0 (в Excel цен не было) — "
                "проставьте реальные цены перед публикацией."
            ))

    # -- построчный импорт ---------------------------------------------------

    def _import_row(self, row, category, kind, dry_run, skip_images):
        article = clean_str(row.get("article"))
        name = clean_str(row.get("name") or row.get("Name"))
        description = clean_str(row.get("description") or row.get("Description"))

        # Разбираем виды грибов ДО построения defaults — is_set зависит от их количества
        mushroom_names = self._resolve_mushroom_types(row.get("mushroom_types"), article, dry_run)

        defaults = {
            "name": name,
            "category": category,
            "description": description,
            "country_of_origin": clean_str(row.get("country_of_origin")),
            "preservation_method": map_choice(
                row.get("preservation_method"), PRESERVATION_METHOD_MAP, "preservation_method", article
            ),
            "release_form": map_choice(row.get("release_form"), RELEASE_FORM_MAP, "release_form", article),
            "package": clean_str(row.get("package")),
            "kit": clean_str(row.get("kit")),
            "ingredients": clean_str(row.get("ingredients")),
            "storage_temp_max": parse_int(row.get("storage_temp_max")),
            "storage_temp_min": parse_int(row.get("storage_temp_min")),
            "shelf_life_months": parse_int(row.get("shelf_life_months")),
            "net_weight": parse_int(row.get("net_weight")),
            "packaging_weight": parse_decimal(row.get("packaging_weight")),
            "packaging_length": parse_decimal(row.get("packaging_length")),
            "packaging_width": parse_decimal(row.get("packaging_width")),
            "packaging_height": parse_decimal(row.get("packaging_height")),
            "total_weight": parse_decimal(row.get("total_weight(kg)") or row.get("total_weight")),
            "nutrition_calories": parse_int(row.get("nutrition_calories")),
            "nutrition_carbs": parse_decimal(row.get("nutrition_carbs")),
            "nutrition_fat": parse_decimal(row.get("nutrition_fat")),
            "nutrition_protein": parse_decimal(row.get("nutrition_protein")),
            "rating": parse_decimal(row.get("rating"), default=Decimal("0")),
            # набор = 2 и более различных видов грибов в строке Excel
            "is_set": len(set(mushroom_names)) > 1,
        }
        if "is_vegetarian" in row.index:
            defaults["is_vegetarian"] = bool(row.get("is_vegetarian")) if not pd.isna(row.get("is_vegetarian")) else False

        image_urls = split_multi(row.get("image"))
        video_urls = split_multi(row.get("Video")) if "Video" in row.index else []

        if dry_run:
            self.stdout.write(
                f"  [dry-run] {article} | {name} | грибы: {mushroom_names} | "
                f"is_set: {defaults['is_set']} | картинок: {len(image_urls)} | видео: {len(video_urls)}"
            )
            return True, False

        with transaction.atomic():
            product, created = Product.objects.update_or_create(article=article, defaults=defaults)

            if mushroom_names:
                types = list(MushroomType.objects.filter(name__in=mushroom_names))
                product.mushroom_types.set(types)
            else:
                product.mushroom_types.clear()

            if not skip_images and (image_urls or video_urls):
                product.images.all().delete()  # переимпорт: пересобираем галерею с нуля
                order = 0
                for url in image_urls:
                    if self._attach_media(product, url, "image", order):
                        order += 1
                for url in video_urls:
                    if self._attach_media(product, url, "video", order):
                        order += 1

        status = "СОЗДАН" if created else "обновлён"
        set_note = " [набор]" if defaults["is_set"] else ""
        self.stdout.write(f"  [+] {article} — {status}{set_note}")
        return created, False

    def _resolve_mushroom_types(self, raw_value, article, dry_run):
        names = []
        for token in split_multi(raw_value):
            key = token.lower().strip()
            mapped_name = MUSHROOM_TYPE_SYNONYMS.get(key)
            if mapped_name:
                names.append(mapped_name)
                continue

            # Нет в словаре синонимов - пробуем найти точное совпадение по имени в БД
            existing = MushroomType.objects.filter(name__iexact=token).first()
            if existing:
                names.append(existing.name)
                continue

            # Совсем неизвестный вид гриба
            self.stdout.write(self.style.WARNING(
                f"  [!] {article}: вид гриба '{token}' не найден в справочнике и не в словаре синонимов."
                + ("" if dry_run else f" Создаю новый MushroomType('{token}') — проверьте вручную.")
            ))
            if not dry_run:
                new_type, _ = MushroomType.objects.get_or_create(name=token.capitalize())
                names.append(new_type.name)
        return names

    # -- медиа: скачивание с диcковым кешем ----------------------------------

    def _attach_media(self, product, url, media_type, order, retries=3, timeout=60):
        content_bytes, filename = self._get_media_content(url, retries=retries, timeout=timeout)
        if content_bytes is None:
            return False

        pi = ProductImage(product=product, media_type=media_type, order=order)
        content = ContentFile(content_bytes)
        if media_type == "image":
            pi.image.save(filename, content, save=False)
        else:
            pi.video.save(filename, content, save=False)
        pi.save()
        return True

    def _get_media_content(self, url, retries=3, timeout=60):
        """
        Возвращает (bytes, filename) для url.

        Если включён дисковый кеш (self.image_cache_dir не None) и файл с этим
        URL уже когда-то скачивался — читает его с диска, не делая HTTP-запрос.
        Иначе скачивает и (если кеш включён) сохраняет в кеш для будущих запусков.
        """
        cache_path = None
        if self.image_cache_dir is not None:
            key = hashlib.sha256(url.encode("utf-8")).hexdigest()
            cache_path = self.image_cache_dir / key
            if cache_path.exists():
                filename = url.rsplit("/", 1)[-1] or key
                self.stdout.write(f"    (кеш) {url}")
                return cache_path.read_bytes(), filename

        resp = None
        last_exc = None
        for attempt in range(1, retries + 1):
            try:
                resp = requests.get(url, timeout=timeout)
                resp.raise_for_status()
                break
            except requests.RequestException as exc:
                last_exc = exc
                if attempt < retries:
                    self.stdout.write(
                        f"    попытка {attempt}/{retries} не удалась ({exc}), пробую снова..."
                    )
                    time.sleep(2 * attempt)  # небольшая пауза перед повтором
                resp = None

        if resp is None:
            self.stderr.write(self.style.ERROR(f"    не удалось скачать {url}: {last_exc}"))
            return None, None

        if cache_path is not None:
            cache_path.write_bytes(resp.content)

        filename = url.rsplit("/", 1)[-1] or "file"
        return resp.content, filename
