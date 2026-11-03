from django.db import migrations


def create_cleanup_schedule(apps, schema_editor):
    """Создаёт ежедневную задачу очистки старых диалогов в django-q."""
    Schedule = apps.get_model("django_q", "Schedule")
    Schedule.objects.get_or_create(
        name="cleanup_old_chat_conversations",
        defaults={
            "func": "chat.tasks.cleanup_old_conversations",
            "schedule_type": "D",
            "repeats": -1,
        },
    )


def remove_cleanup_schedule(apps, schema_editor):
    Schedule = apps.get_model("django_q", "Schedule")
    Schedule.objects.filter(name="cleanup_old_chat_conversations").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("chat", "0002_alter_conversation_options_conversation_user_and_more"),
        ("django_q", "0019_alter_task_options_alter_ormq_key_alter_ormq_lock_and_more"),
    ]

    operations = [
        migrations.RunPython(create_cleanup_schedule, remove_cleanup_schedule),
    ]
