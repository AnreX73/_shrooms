from collections import Counter, defaultdict

from django.core.management.base import BaseCommand

from shop.models import Product


def weight_bucket(w):
    return ((w + 25) // 50) * 50


def print_histogram(stdout, style, counter, indent=""):
    if not counter:
        stdout.write(f"{indent}  (нет данных)")
        return
    max_count = max(counter.values())
    for bucket in sorted(counter):
        count = counter[bucket]
        bar_len = max(1, int(count / max_count * 40)) if max_count else 0
        bar = "█" * bar_len
        stdout.write(f"{indent}{bucket:>5} г | {count:>3} | {bar}")


class Command(BaseCommand):
    help = "Диагностика поля net_weight: распределение по бакетам, разбивка по категориям, ассорти"

    def add_arguments(self, parser):
        parser.add_argument(
            "--bucket-step",
            type=int,
            default=50,
            help="Шаг бакета в граммах (по умолчанию 50)",
        )

    def handle(self, *args, **options):
        style = self.style
        total = Product.objects.count()
        self.stdout.write(f"Всего товаров: {total}\n")

        # --- Общая картина ---
        qs = Product.objects.values_list(
            "id", "name", "is_set", "net_weight", "category_id", "category__name"
        )

        with_weight = [p for p in qs if p[3] is not None]
        without_weight = [p for p in qs if p[3] is None]

        self.stdout.write(style.SUCCESS(f"=== С net_weight: {len(with_weight)} ==="))
        self.stdout.write(
            style.WARNING(f"=== БЕЗ net_weight (null): {len(without_weight)} ===\n")
        )

        raw_values = sorted({p[3] for p in with_weight})
        self.stdout.write(
            f"Уникальных сырых значений веса (по всем категориям): {len(raw_values)}"
        )
        if raw_values:
            self.stdout.write(
                f"Мин/Макс по всей базе: {min(raw_values)} / {max(raw_values)}"
            )
        self.stdout.write("")

        # --- Разбивка по категориям ---
        self.stdout.write(style.SUCCESS("=== Распределение веса ПО КАТЕГОРИЯМ ==="))

        by_category = defaultdict(list)
        for _id, name, is_set, w, cat_id, cat_name in with_weight:
            by_category[(cat_id, cat_name)].append(w)

        category_summary = []

        for (cat_id, cat_name), weights in sorted(
            by_category.items(), key=lambda x: x[0][1] or ""
        ):
            bucket_counter = Counter(weight_bucket(w) for w in weights)
            self.stdout.write(
                f"\n--- {cat_name or '(без названия)'} (id={cat_id}) | товаров с весом: {len(weights)} ---"
            )
            self.stdout.write(f"  Мин/Макс сырой вес: {min(weights)} / {max(weights)}")
            print_histogram(self.stdout, style, bucket_counter, indent="  ")
            category_summary.append(
                (cat_name, min(weights), max(weights), len(bucket_counter))
            )

        # --- Пересекаются ли диапазоны категорий? ---
        self.stdout.write(
            style.SUCCESS(
                "\n=== Сводка диапазонов по категориям (для решения: общий фильтр или per-category) ==="
            )
        )
        for cat_name, mn, mx, n_buckets in category_summary:
            self.stdout.write(
                f"  {cat_name or '(без названия)':<25} диапазон: {mn:>4}-{mx:<4} г | бакетов: {n_buckets}"
            )

        overlaps = self._check_overlap(category_summary)
        if overlaps:
            self.stdout.write(
                style.WARNING(
                    "\n  Диапазоны категорий ПЕРЕСЕКАЮТСЯ — единый список бакетов для всех категорий адекватен."
                )
            )
        else:
            self.stdout.write(
                style.WARNING(
                    "\n  Диапазоны категорий НЕ пересекаются (например, сушёные лёгкие / консервы в рассоле тяжёлые) —\n"
                    "  возможно, стоит показывать РАЗНЫЙ список чекбоксов весов в зависимости от выбранной категории."
                )
            )

        # --- Погранзначения ---
        self.stdout.write(
            style.SUCCESS(
                f"\n=== Погранзначения (близко к границе бакета, шаг {options['bucket_step']}г) ==="
            )
        )
        step = options["bucket_step"]
        half = step // 2
        borderline = []
        for _id, name, is_set, w, cat_id, cat_name in with_weight:
            mod = w % step
            if abs(mod - half) <= 3:
                borderline.append((_id, name, w, cat_name))
        if borderline:
            for _id, name, w, cat_name in borderline:
                self.stdout.write(
                    f"  id={_id} '{name}' [{cat_name}]: {w}г -> бакет {weight_bucket(w)}г"
                )
        else:
            self.stdout.write(
                "  Нет пограничных значений — данные хорошо кластеризованы."
            )

        # --- Ассорти ---
        self.stdout.write(
            style.SUCCESS("\n=== Ассорти (is_set=True) по категориям ===")
        )
        sets = Product.objects.filter(is_set=True).select_related("category")
        sets_total = sets.count()
        self.stdout.write(f"Всего ассорти: {sets_total}")

        sets_by_cat = defaultdict(lambda: {"with": 0, "without": 0})
        for p in sets:
            key = p.category.name if p.category else "(без категории)"
            if p.net_weight is not None:
                sets_by_cat[key]["with"] += 1
            else:
                sets_by_cat[key]["without"] += 1

        for cat_name, counts in sorted(sets_by_cat.items()):
            self.stdout.write(
                f"  {cat_name:<25} с весом: {counts['with']:>3} | без веса: {counts['without']:>3}"
            )

        without_weight_sets = sets.filter(net_weight__isnull=True)
        if without_weight_sets.exists():
            self.stdout.write(style.WARNING("\n  Примеры ассорти без веса:"))
            for p in without_weight_sets[:10]:
                self.stdout.write(f"    id={p.id} '{p.name}' [{p.category}]")

        # --- Не-ассорти без веса (аномалия) ---
        anomalies = Product.objects.filter(
            is_set=False, net_weight__isnull=True
        ).select_related("category")
        if anomalies.exists():
            self.stdout.write(
                style.ERROR(
                    f"\n=== ВНИМАНИЕ: {anomalies.count()} обычных товаров (не ассорти) БЕЗ net_weight ==="
                )
            )
            for p in anomalies[:15]:
                self.stdout.write(f"    id={p.id} '{p.name}' [{p.category}]")

    def _check_overlap(self, category_summary):
        ranges = [(mn, mx) for _, mn, mx, _ in category_summary]
        for i in range(len(ranges)):
            for j in range(i + 1, len(ranges)):
                a_min, a_max = ranges[i]
                b_min, b_max = ranges[j]
                if a_min <= b_max and b_min <= a_max:
                    return True
        return False
