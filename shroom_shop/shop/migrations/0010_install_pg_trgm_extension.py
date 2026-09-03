# shroom_shop/shop/migrations/0009_info_created_at_info_updated_at_and_more.py
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        # Укажите здесь последнюю миграцию вашего приложения
        ("shop", "0009_info_created_at_info_updated_at_and_more"),
    ]

    operations = [
        migrations.RunSQL(
            "CREATE EXTENSION IF NOT EXISTS pg_trgm;",
            reverse_sql="DROP EXTENSION IF EXISTS pg_trgm;",
        ),
    ]
