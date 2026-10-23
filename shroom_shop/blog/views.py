from django.conf import settings
from django.core.exceptions import ValidationError
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from .models import Post, PostBlock, PostImage
from .forms import PostForm
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
import uuid
from django.contrib import messages
import bleach
from bleach.css_sanitizer import CSSSanitizer

from shroom_shop.seo import absolute_url, image_url, json_ld, make_description


from django.http import HttpResponse
from django.db.models import Max, Prefetch
from django.views.decorators.http import require_POST
from django_q.tasks import async_task

from django.db import transaction

# ALLOWED_TAGS / ALLOWED_ATTRS / css_sanitizer — уже существуют для clean_rich_text, не трогаем

EMBED_ALLOWED_TAGS = ['iframe']
EMBED_ALLOWED_ATTRS = {
    'iframe': ['src', 'width', 'height', 'frameborder', 'allow', 'allowfullscreen', 'title']
}

def clean_embed_code(raw_html: str) -> str:
    if not raw_html:
        return ''
    return bleach.clean(
        raw_html,
        tags=EMBED_ALLOWED_TAGS,
        attributes=EMBED_ALLOWED_ATTRS,
        strip=True,
    )

User = get_user_model()


def superuser_required(view_func):
    """Декоратор для superuser"""
    decorated = login_required(user_passes_test(lambda u: u.is_superuser)(view_func))
    return decorated


def blog_page(request, slug):
    blocks_prefetch = Prefetch(
        "blocks",
        queryset=PostBlock.objects.prefetch_related("images").order_by("order"),
    )
    post = get_object_or_404(
        Post.objects.prefetch_related(blocks_prefetch),
        slug=slug,
        is_published=True,
    )
    posts = (
        Post.objects.filter(is_published=True)
        .prefetch_related(blocks_prefetch)
        .order_by("-published_at")
        .exclude(id=post.id)
    )
    post_text = next(
        (
            block.text
            for block in post.blocks.all()
            if block.block_type == "text" and block.text
        ),
        "",
    )
    post_url = absolute_url(reverse("blog:blog_page", args=[post.slug]))
    published_at = post.published_at or post.created_at
    seo_image = image_url(post.cover_image)

    article = {
        "@type": "Article",
        "headline": post.title,
        "description": make_description(
            post.excerpt or post_text, fallback=settings.SITE_DESCRIPTION
        ),
        "datePublished": published_at.isoformat(),
        "dateModified": published_at.isoformat(),
        "mainEntityOfPage": post_url,
        "author": {"@type": "Organization", "name": settings.SITE_NAME},
        "publisher": {"@type": "Organization", "name": settings.SITE_NAME},
        "inLanguage": "ru-RU",
    }
    if seo_image:
        article["image"] = [seo_image]

    context = {
        "posts": posts,
        "post": post,
        "seo_title": f"{post.title} — {settings.SITE_NAME}",
        "seo_description": make_description(
            post.excerpt or post_text, fallback=settings.SITE_DESCRIPTION
        ),
        "seo_canonical": post_url,
        "seo_image": seo_image,
        "seo_og_type": "article",
        "seo_json_ld": json_ld(
            {"@context": "https://schema.org", "@graph": [article]}
        ),
    }
    return render(request, "blog/blog.html", context=context)


@superuser_required
def post_create(request):
    """
    Не показывает форму сам по себе — создаёт пустой draft-пост
    и сразу уводит на post_edit, где живёт вся логика с блоками,
    Dropzone-загрузками и Sortable.
    """
    draft = Post.objects.create(
        title="Черновик",
        slug=f"draft-{uuid.uuid4().hex[:8]}",
        is_published=False,
    )
    return redirect("blog:post_edit", pk=draft.pk)


@superuser_required
def post_edit(request, pk):
    post = get_object_or_404(Post, pk=pk)

    if request.method == "POST":
        post_form = PostForm(request.POST, request.FILES, instance=post)
        if post_form.is_valid():
            action = request.POST.get("action")

            if action == "publish":
                post_form.instance.is_published = True
            elif action == "unpublish":
                post_form.instance.is_published = False
            # action == 'save_draft' — is_published не трогаем вообще, оставляем как было

            post = post_form.save()

            if action == "publish":
                messages.success(request, "Пост опубликован")
                return redirect("blog:blog_page", slug=post.slug)

            if action == "unpublish":
                messages.success(request, "Пост снят с публикации")
            else:
                messages.info(
                    request,
                    "Пост сохранён"
                    if post.is_published
                    else "Черновик сохранён",
                )
            return redirect("blog:post_edit", pk=post.pk)
    else:
        post_form = PostForm(instance=post)

    return render(
        request, "blog/post_edit.html", {"post_form": post_form, "post": post}
    )


def _delete_file(field_file):
    """Удаляет файл с диска, не трогая запись в БД."""
    if field_file:
        field_file.delete(save=False)


@superuser_required
@require_POST
def post_delete(request, pk):
    """Удаляет пост вместе с файлами (обложка, медиа блоков и галерей)."""
    post = get_object_or_404(Post, pk=pk)
    title = post.title

    for block in post.blocks.prefetch_related("images"):
        _delete_file(block.single_image)
        _delete_file(block.video_original)
        _delete_file(block.video_processed)
        _delete_file(block.video_poster)
        for image in block.images.all():
            _delete_file(image.image)

    _delete_file(post.cover_image)
    post.delete()  # блоки, галереи и картинки удаляются каскадом

    messages.success(request, f"Пост «{title}» удалён.")
    return redirect("blog:post_choice")


def block_add(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    max_order = post.blocks.aggregate(m=Max("order"))["m"] or 0
    block = PostBlock.objects.create(post=post, block_type="text", order=max_order + 1)
    return render(request, "blog/partials/block_row.html", {"block": block})


ALLOWED_TAGS = ["strong", "b", "br", "span", "p", "font"]
ALLOWED_ATTRS = {"span": ["style"], "font": ["color"]}
ALLOWED_STYLES = ["color"]

css_sanitizer = CSSSanitizer(allowed_css_properties=ALLOWED_STYLES)


def clean_rich_text(html):
    return bleach.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRS,
        css_sanitizer=css_sanitizer,
        strip=True,
    )


@superuser_required
def block_update(request, pk):
    block = get_object_or_404(PostBlock, pk=pk)
    if request.method == 'POST':
        block.block_type = request.POST.get('block_type', block.block_type)

        raw_text = request.POST.get('text', '')
        block.text = clean_rich_text(raw_text) if raw_text else ''

        block.video_url = request.POST.get('video_url', '')

        raw_embed = request.POST.get('embed_code', '')
        block.embed_code = clean_embed_code(raw_embed)

        # embed_code важнее ссылки — не путаем, что рендерить
        if block.embed_code:
            block.video_url = ''

        try:
            block.full_clean(exclude=['post'])
        except ValidationError as e:
            messages.error(request, '; '.join(e.messages))
            return render(request, 'blog/partials/block_row.html', {'block': block})

        block.save()
    return render(request, 'blog/partials/block_row.html', {'block': block})


def block_delete(request, pk):
    PostBlock.objects.filter(pk=pk).delete()
    return HttpResponse("")  # htmx просто уберёт элемент из DOM


def main_page_confirm(request, pk):
    """Возвращает модалку — либо с предупреждением о замене, либо сразу подтверждение снятия."""
    post = get_object_or_404(Post, pk=pk)
    current = Post.objects.filter(published_on_main_page=True).exclude(pk=pk).first()
    return render(
        request,
        "blog/partials/main_page_modal.html",
        {
            "post": post,
            "current": current,
        },
    )


def main_page_toggle(request, pk):
    """Реальное переключение — минуя Post.save(), чтобы не задевать slug/published_at логику."""
    post = get_object_or_404(Post, pk=pk)

    with transaction.atomic():
        if post.published_on_main_page:
            Post.objects.filter(pk=pk).update(published_on_main_page=False)
        else:
            Post.objects.filter(published_on_main_page=True).exclude(pk=pk).update(
                published_on_main_page=False
            )
            Post.objects.filter(pk=pk).update(published_on_main_page=True)

    post.refresh_from_db(fields=["published_on_main_page"])
    return render(request, "blog/partials/main_page_button.html", {"post": post})


def block_reorder(request):
    # htmx шлёт список id блоков в новом порядке
    ids = request.POST.getlist("block_id")
    for index, block_id in enumerate(ids):
        PostBlock.objects.filter(pk=block_id).update(order=index)
    return HttpResponse(status=204)


def upload_gallery_image(request, pk):
    block = get_object_or_404(PostBlock, pk=pk)
    order = block.images.count()
    img = PostImage.objects.create(
        block=block, image=request.FILES["file"], order=order
    )
    return render(request, "blog/partials/gallery_thumb.html", {"image": img})


def delete_gallery_image(request, pk):
    PostImage.objects.filter(pk=pk).delete()
    return HttpResponse("")


def upload_short_video(request, pk):
    block = get_object_or_404(PostBlock, pk=pk)
    block.video_original = request.FILES["file"]
    block.video_status = "pending"
    block.save()
    async_task("blog.tasks.process_short_video", block.id)
    return render(request, "blog/partials/video_status.html", {"block": block})


def block_video_status(request, pk):
    block = get_object_or_404(PostBlock, pk=pk)
    return render(request, "blog/partials/video_status.html", {"block": block})


# views.py
def upload_single_image(request, pk):
    block = get_object_or_404(PostBlock, pk=pk)
    block.single_image = request.FILES["file"]
    block.save()
    return render(request, "blog/partials/single_image_preview.html", {"block": block})


@superuser_required
def post_choice(request):
    posts = Post.objects.all()
    return render(request, "blog/post_choice.html", {"posts": posts})
