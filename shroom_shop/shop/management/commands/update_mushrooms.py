from django.core.management.base import BaseCommand
from django.db import transaction
from shop.models import (
    Product,
    MushroomType,
)  # Замените your_app на имя вашего приложения


class Command(BaseCommand):
    help = "Привязывает указанный вид грибов к продуктам, содержащим это название"

    def add_arguments(self, parser):
        # Добавляем обязательный позиционный аргумент
        parser.add_argument(
            "mushroom_name",
            type=str,
            help="Название вида гриба (например, Маслята или Лисички)",
        )

    def handle(self, *args, **options):
        # Получаем имя гриба из аргументов командной строки
        mushroom_name = options["mushroom_name"]

        # 1. Получаем или создаем вид гриба
        mushroom_type, created = MushroomType.objects.get_or_create(name=mushroom_name)
        if created:
            self.stdout.write(
                self.style.SUCCESS(f'Создан новый вид гриба: "{mushroom_name}"')
            )

        # 2. Фильтруем продукты по переданному имени
        products = Product.objects.filter(name__icontains=mushroom_name)
        total_products = products.count()

        if total_products == 0:
            self.stdout.write(
                self.style.WARNING(
                    f'Продукты, содержащие в названии "{mushroom_name}", не найдены.'
                )
            )
            return

        self.stdout.write(f"Найдено продуктов для обработки: {total_products}")

        # 3. Безопасно добавляем связь, не трогая старые
        with transaction.atomic():
            for product in products.iterator():
                # .add() только добавляет новую связь и никогда не удаляет существующие
                product.mushroom_types.add(mushroom_type)

        self.stdout.write(
            self.style.SUCCESS(
                f'Успешно обработано продуктов для гриба "{mushroom_name}": {total_products}'
            )
        )
