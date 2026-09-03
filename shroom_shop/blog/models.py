from django.db import models
from django.db import transaction
from .utils import make_slug
from django.utils import timezone

import re
from django.core.exceptions import ValidationError
from django.utils.safestring import mark_safe
from django.utils.html import escape


class Post(models.Model):
    CATEGORY_CHOICES = [
        ("story", "История"),
        ("recipe", "Рецепт"),
        ("media", "Видео/интервью"),
    ]
    title = models.CharField(max_length=255, verbose_name="Заголовок")
    slug = models.SlugField(unique=True, verbose_name="URL (slug)")
    excerpt = models.TextField(blank=True, verbose_name="Краткое описание")
    cover_image = models.ImageField(
        upload_to="posts/covers/", verbose_name="Обложка", blank=True, null=True
    )
    category = models.CharField(
        max_length=50, choices=CATEGORY_CHOICES, verbose_name="Категория"
    )
    is_published = models.BooleanField(default=False, verbose_name="Опубликовано")
    published_on_main_page = models.BooleanField(
        default=False, verbose_name="На главной странице"
    )
    published_at = models.DateTimeField(
        null=True, blank=True, verbose_name="Опубликовано(дата и время)"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["published_on_main_page"],
                condition=models.Q(published_on_main_page=True),
                name="unique_post_on_main_page",
            ),
        ]

    def save(self, *args, **kwargs):
        old_is_published = False
        if self.pk:
            old_is_published = (
                Post.objects.filter(pk=self.pk)
                .values_list("is_published", flat=True)
                .first()
                or False
            )

        if not self.is_published:
            self.slug = make_slug(self.title, exclude_pk=self.pk)
        elif self.is_published and not old_is_published:
            self.slug = make_slug(self.title, exclude_pk=self.pk)

        if self.is_published and not self.published_at:
            self.published_at = timezone.now()
        if not self.is_published:
            self.published_at = None

        if self.published_on_main_page:
            with transaction.atomic():
                Post.objects.select_for_update().filter(
                    published_on_main_page=True
                ).exclude(pk=self.pk).update(published_on_main_page=False)
                super().save(*args, **kwargs)
        else:
            super().save(*args, **kwargs)


class PostBlock(models.Model):
    BLOCK_TYPES = [
        ("text", "Текст"),
        ("image", "Одно фото"),
        ("gallery", "Галерея (swiper)"),
        ("video_embed", "Видео (ссылка YouTube/VK)"),
        ("short_video", "Короткое видео (вертикальное)"),
        ("quote", "Цитата"),
    ]
    VIDEO_STATUS = [
        ("empty", "Видео не загружено"),
        ("pending", "В очереди"),
        ("processing", "Обрабатывается"),
        ("ready", "Готово"),
        ("failed", "Ошибка"),
    ]

    post = models.ForeignKey(
        Post, related_name="blocks", on_delete=models.CASCADE, verbose_name="Пост"
    )
    order = models.PositiveIntegerField(default=0)
    block_type = models.CharField(
        max_length=20, choices=BLOCK_TYPES, verbose_name="Тип блока"
    )
    text = models.TextField(blank=True, verbose_name="Текст")
    video_url = models.URLField(blank=True, verbose_name="URL видео")
    embed_code = models.TextField(
        blank=True,
        verbose_name="Произвольный embed-код (iframe)",
        help_text="Заполняйте, если площадка не из списка поддерживаемых (не YouTube/VK)",
    )
    single_image = models.ImageField(
        upload_to="posts/blocks/", blank=True, null=True, verbose_name="Одно фото"
    )

    # поля для short_video
    video_original = models.FileField(
        upload_to="posts/video/original/", blank=True, null=True
    )
    video_processed = models.FileField(
        upload_to="posts/video/processed/", blank=True, null=True
    )
    video_poster = models.ImageField(
        upload_to="posts/video/posters/", blank=True, null=True
    )
    video_status = models.CharField(
        max_length=20, choices=VIDEO_STATUS, default="empty", blank=True
    )
    video_duration = models.FloatField(null=True, blank=True)

    YOUTUBE_RE = re.compile(
        r"(?:youtube\.com/watch\?v=|youtube\.com/shorts/|youtu\.be/|youtube\.com/embed/)([\w-]{11})"
    )
    VK_RE = re.compile(r"vk(?:video)?\.(?:ru|com)/video(-?\d+)_(\d+)")

    class Meta:
        ordering = ["order"]

    def clean(self):
        if self.block_type == "video_embed" and self.video_url and self.embed_code:
            raise ValidationError(
                "Заполните либо ссылку, либо embed-код, не оба сразу."
            )

    def get_embed_html(self):
        """
        HTML для вставки видео в video_embed блоке.
        Приоритет: embed_code -> автопарсинг YouTube -> автопарсинг VK -> просто ссылка.
        """
        if self.block_type != "video_embed":
            return ""

        if self.embed_code:
            return mark_safe(self.embed_code)

        if not self.video_url:
            return ""

        match = self.YOUTUBE_RE.search(self.video_url)
        if match:
            video_id = match.group(1)
            return mark_safe(
                f'<div class="video-embed video-embed--youtube">'
                f'<iframe src="https://www.youtube.com/embed/{video_id}" '
                f'title="YouTube video" frameborder="0" allowfullscreen '
                f'allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"></iframe>'
                f"</div>"
            )

        match = self.VK_RE.search(self.video_url)
        if match:
            oid, vid = match.groups()
            return mark_safe(
                f'<div class="video-embed video-embed--vk">'
                f'<iframe src="https://vk.com/video_ext.php?oid={oid}&id={vid}" '
                f'frameborder="0" allowfullscreen></iframe>'
                f"</div>"
            )

        safe_url = escape(self.video_url)
        return mark_safe(
            f'<a href="{safe_url}" target="_blank" rel="noopener noreferrer">Смотреть видео</a>'
        )


class PostImage(models.Model):
    block = models.ForeignKey(
        PostBlock, related_name="images", on_delete=models.CASCADE
    )
    image = models.ImageField(upload_to="posts/gallery/")
    caption = models.CharField(max_length=255, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]
