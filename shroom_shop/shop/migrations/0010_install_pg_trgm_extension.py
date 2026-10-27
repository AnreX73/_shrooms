from django.db import migrations


def create_extension(apps, schema_editor):
    """pg_trgm нужен для поиска по артикулу; в SQLite (тесты) его нет."""
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")


def drop_extension(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("DROP EXTENSION IF EXISTS pg_trgm;")


class Migration(migrations.Migration):
    dependencies = [
        # Укажите здесь последнюю миграцию вашего приложения
        ("shop", "0009_info_created_at_info_updated_at_and_more"),
    ]

    operations = [
        migrations.RunPython(create_extension, drop_extension),
    ]
