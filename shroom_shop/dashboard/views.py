import io


import json
import os
import random
from itertools import chain

import openpyxl
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

from django.contrib.postgres.search import TrigramSimilarity
from django.db import models
from django.db import models as db_models
from django.db.models.functions import Lower
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View
from django.views.decorators.http import require_http_methods, require_POST
from django.views.generic import TemplateView
from django_q.tasks import async_task
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from shop.models import Category, Info, MushroomType, Order, OrderItem, Product, ProductImage

from .forms import CategoryForm, MushroomTypeForm, ProductForm, StartBannerForm

from django.contrib import messages
from django.urls import reverse



User = get_user_model()
is_manager = lambda u: u.is_staff


class AdminDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = "dashboard/admin_area.html"

    # Проверка, что зашел именно админ/стафф
    def test_func(self):
        return self.request.user.is_superuser


# ── Миксин для проверки is_superuser ──────────────────────────────────────────
class SuperuserRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_superuser


def superuser_required(view_func):
    """Декоратор для function-based views"""
    decorated = login_required(user_passes_test(lambda u: u.is_superuser)(view_func))
    return decorated


# ── Шаг 1: Создание товара ────────────────────────────────────────────────────
class ProductCreateView(SuperuserRequiredMixin, View):
    template_name = "dashboard/product_form.html"

    def get(self, request):
        form = ProductForm()
        names = list(
            Product.objects.values_list("name", flat=True).distinct().order_by("name")
        )
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "title": "Добавить товар",
                "is_edit": False,
                "product_names_json": json.dumps(names, ensure_ascii=False),
            },
        )

    def post(self, request):
        form = ProductForm(request.POST)
        if form.is_valid():
            # form.save() сам вызовет save_m2m(), т.к. commit=True по умолчанию —
            # отдельный проход по mushroom_types не нужен
            product = form.save()
            return redirect("dashboard:product_media", pk=product.pk)

        names = list(
            Product.objects.values_list("name", flat=True).distinct().order_by("name")
        )
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "title": "Добавить товар",
                "is_edit": False,
                "product_names_json": json.dumps(names, ensure_ascii=False),
            },
        )


# ── Шаг 1: Редактирование товара ──────────────────────────────────────────────
class ProductEditView(SuperuserRequiredMixin, View):
    template_name = "dashboard/product_form.html"

    def get(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        form = ProductForm(instance=product)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "product": product,
                "title": f"Редактировать: {product.name}",
                "is_edit": True,
            },
        )

    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            # form.save() сам вызывает save_m2m() — mushroom_types
            # обновится без ручного delete()/create()
            form.save()
            return redirect("dashboard:product_media", pk=product.pk)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "product": product,
                "title": f"Редактировать: {product.name}",
                "is_edit": True,
            },
        )


# ── Шаг 1: Создание товара на основе существующего ───────────────────────────
class ProductCloneView(SuperuserRequiredMixin, View):
    template_name = "dashboard/product_form.html"

    def get(self, request, pk):
        source = get_object_or_404(Product, pk=pk)
        form = ProductForm(instance=source)
        # instance=source подтягивает и mushroom_types как initial —
        # чекбоксы отрисуются уже отмеченными, current_shades тут не нужен
        form.initial["article"] = ""
        form.fields["article"].widget.attrs.update(
            {
                "autofocus": True,
                "placeholder": f"сменить !!!: {source.article}",
            }
        )
        names = list(
            Product.objects.values_list("name", flat=True).distinct().order_by("name")
        )
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "title": f"Клонировать: {source.name}",
                "is_edit": False,
                "product_names_json": json.dumps(names, ensure_ascii=False),
            },
        )

    def post(self, request, pk):
        # instance НЕ передаём — форма создаст новый объект,
        # mushroom_types придут из request.POST как обычно для M2M
        form = ProductForm(request.POST)
        if form.is_valid():
            product = form.save()
            return redirect("dashboard:product_media", pk=product.pk)

        source = get_object_or_404(Product, pk=pk)
        names = list(
            Product.objects.values_list("name", flat=True).distinct().order_by("name")
        )
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "title": f"Клонировать: {source.name}",
                "is_edit": False,
                "product_names_json": json.dumps(names, ensure_ascii=False),
            },
        )

    # ── Шаг 2: Страница медиа ─────────────────────────────────────────────────────


class ProductMediaView(SuperuserRequiredMixin, View):
    template_name = "dashboard/product_media.html"

    def get(self, request, pk):
        product = get_object_or_404(Product.objects.prefetch_related("images"), pk=pk)
        return render(
            request,
            self.template_name,
            {
                "product": product,
                "title": f"Медиа: {product.name}",
            },
        )


# ── AJAX: загрузка одного файла ───────────────────────────────────────────────
@superuser_required
@require_POST
def upload_product_media(request, pk):
    product = get_object_or_404(Product, pk=pk)
    file = request.FILES.get("file")
    if not file:
        return JsonResponse({"error": "Файл не передан"}, status=400)

    ext = os.path.splitext(file.name)[1].lower()
    is_video = ext in {".mp4", ".mov", ".avi", ".webm"}
    media_type = "video" if is_video else "image"

    last_order = (
        product.images.aggregate(max_order=db_models.Max("order"))["max_order"] or 0
    )

    obj = ProductImage(
        product=product,
        media_type=media_type,
        order=last_order + 1,
        status="pending",
    )
    if is_video:
        obj.video = file
    else:
        obj.image = file
    obj.save()

    if not is_video:
        async_task(
            "dashboard.tasks.compress_product_image",
            obj.pk,
            task_name=f"compress_image_{obj.pk}",
        )
    else:
        async_task(
            "dashboard.tasks.compress_product_video",
            obj.pk,
            task_name=f"compress_video_{obj.pk}",
        )

    return JsonResponse(
        {
            "id": obj.pk,
            "media_type": media_type,
            "status": obj.status,
            "preview_url": obj.preview_url,
        }
    )


# ── AJAX: новый порядок файлов ────────────────────────────────────────────────
@superuser_required
@require_POST
def reorder_product_media(request, pk):
    try:
        data = json.loads(request.body)
        ids = data.get("order", [])
    except (json.JSONDecodeError, KeyError):
        return JsonResponse({"error": "Неверный формат"}, status=400)

    for index, media_id in enumerate(ids):
        ProductImage.objects.filter(pk=media_id, product_id=pk).update(order=index)

    return JsonResponse({"ok": True})


# ── AJAX: удаление файла ──────────────────────────────────────────────────────
@superuser_required
@require_POST
def delete_product_media(request, media_id):
    obj = get_object_or_404(ProductImage, pk=media_id)
    for field in (obj.image, obj.image_compressed, obj.video):
        if field:
            field.delete(save=False)
    obj.delete()
    return JsonResponse({"ok": True})


# ── AJAX: статус обработки одного файла (HTMX polling) ───────────────────────
@superuser_required
def media_status(request, media_id):
    obj = get_object_or_404(ProductImage, pk=media_id)
    return JsonResponse({"status": obj.status, "preview_url": obj.preview_url})


# ── HTMX: частичный шаблон одного медиа-элемента ─────────────────────────────
@superuser_required
def media_item_partial(request, media_id):
    obj = get_object_or_404(ProductImage, pk=media_id)
    return render(request, "dashboard/partials/media_item.html", {"media": obj})


# ─────────────────────────────────────────────────────────────
# Вспомогательная функция — рендерит partial карточки
# ─────────────────────────────────────────────────────────────


def _card_response(request, order):
    order = (
        Order.objects.select_related("user", "assigned_manager")
        .prefetch_related("items__product__images")
        .get(pk=order.pk)
    )
    managers = User.objects.filter(is_staff=True)
    return render(
        request,
        "dashboard/partials/_order_card.html",
        {
            "order": order,
            "managers": managers,
            "is_superuser": request.user.is_superuser,
        },
    )


# ─────────────────────────────────────────────────────────────
# Главная страница
# ─────────────────────────────────────────────────────────────


@login_required
@user_passes_test(is_manager)
def manage_orders(request):
    orders = (
        Order.objects.filter(is_archived=False)  # ← добавить
        .select_related("user", "assigned_manager")
        .prefetch_related("items__product__images")
        .order_by("-created_at")
    )
    managers = User.objects.filter(is_staff=True)

    if request.user.is_superuser:
        # Суперюзер: смотрит сессию — выбран ли конкретный менеджер
        active_manager_id = request.session.get("active_manager_id")
        active_manager = (
            managers.filter(id=active_manager_id).first() if active_manager_id else None
        )
        if active_manager:
            orders = orders.filter(assigned_manager=active_manager)
        # если active_manager = None — видит все заказы
    else:
        # Обычный менеджер — только свои заказы
        active_manager = request.user
        orders = orders.filter(
            models.Q(assigned_manager=request.user) | models.Q(assigned_manager=None)
        )

    return render(
        request,
        "dashboard/manage_orders.html",
        {
            "title": "Управление заказами",
            "orders": orders,
            "managers": managers,
            "active_manager": active_manager,
            "is_superuser": request.user.is_superuser,
        },
    )


# ─────────────────────────────────────────────────────────────
# Переключение активного менеджера (только для суперюзера)
# ─────────────────────────────────────────────────────────────


@login_required
@user_passes_test(lambda u: u.is_superuser)
@require_POST
def set_active_manager(request):
    manager_id = request.POST.get("manager_id")
    if manager_id:
        request.session["active_manager_id"] = int(manager_id)
    else:
        request.session.pop("active_manager_id", None)
    # HX-Refresh перезагружает всю страницу через HTMX
    from django.http import HttpResponse

    return HttpResponse(status=204, headers={"HX-Refresh": "true"})


# ─────────────────────────────────────────────────────────────
# Назначить менеджера на заказ
# ─────────────────────────────────────────────────────────────


@login_required
@user_passes_test(is_manager)
@require_POST
def order_assign(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    if not order.assigned_manager:
        if request.user.is_superuser:
            # Суперюзер назначает выбранного менеджера из select
            manager_id = request.POST.get("manager_id")
            manager = get_object_or_404(User, id=manager_id, is_staff=True)
        else:
            # Обычный менеджер берёт себе
            manager = request.user
        order.assigned_manager = manager
        order.status = "confirmed"
        order.save(update_fields=["assigned_manager", "status", "updated_at"])
    return _card_response(request, order)


# ─────────────────────────────────────────────────────────────
# Галочка «товар собран»
# ─────────────────────────────────────────────────────────────


@login_required
@user_passes_test(is_manager)
@require_POST
def order_item_toggle(request, item_id):
    item = get_object_or_404(OrderItem, id=item_id)
    item.is_collected = not item.is_collected
    item.save(update_fields=["is_collected"])
    order = Order.objects.get(pk=item.order_id)
    return _card_response(request, order)


# ─────────────────────────────────────────────────────────────
# Статус → «В обработке»  (все товары должны быть собраны)
# ─────────────────────────────────────────────────────────────


@login_required
@user_passes_test(is_manager)
@require_POST
def order_set_processing(request, order_id):
    order = get_object_or_404(Order.objects.prefetch_related("items"), id=order_id)
    if not order.items.filter(is_collected=False).exists():
        order.status = "processing"
        order.save(update_fields=["status", "updated_at"])
    return _card_response(request, order)


# ─────────────────────────────────────────────────────────────
# Статус → «Отправлен»  (+ опциональный трек-номер)
# ─────────────────────────────────────────────────────────────


@login_required
@user_passes_test(is_manager)
@require_POST
def order_ship(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    tracking = request.POST.get("tracking_number", "").strip()
    if tracking:
        order.tracking_number = tracking
    order.status = "shipped"
    order.save(update_fields=["status", "tracking_number", "updated_at"])
    return _card_response(request, order)


# ─────────────────────────────────────────────────────────────
# Статус → «Доставлен»
# ─────────────────────────────────────────────────────────────


@login_required
@user_passes_test(is_manager)
@require_POST
def order_deliver(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    order.status = "delivered"
    order.delivered_at = timezone.now()
    order.save(update_fields=["status", "delivered_at", "updated_at"])
    return _card_response(request, order)


# ─────────────────────────────────────────────────────────────
# Отменить заказ
# ─────────────────────────────────────────────────────────────


@login_required
@user_passes_test(is_manager)
@require_POST
def order_cancel(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    if order.status not in ("delivered", "shipped"):
        order.status = "cancelled"
        order.save(update_fields=["status", "updated_at"])
    return _card_response(request, order)


@login_required
@user_passes_test(is_manager)
def order_note_form(request, order_id):
    """GET — показать форму редактирования"""
    order = get_object_or_404(Order, id=order_id)
    return render(request, "dashboard/partials/_order_note_form.html", {"order": order})


@login_required
@user_passes_test(is_manager)
@require_POST
def order_save_note(request, order_id):
    """POST — сохранить и вернуть блок с примечанием"""
    order = get_object_or_404(Order, id=order_id)
    order.assigned_manager_note = request.POST.get("assigned_manager_note", "").strip()
    order.save(update_fields=["assigned_manager_note", "updated_at"])
    return render(request, "dashboard/partials/_order_note.html", {"order": order})


# # ─────────────────────────────────────────────────────────────
# # Webhook от платёжной системы
# # ─────────────────────────────────────────────────────────────


# @require_POST
# def order_payment_webhook(request, order_id):
#     # Раскомментируй и настрой проверку подписи под свою платёжку:
#     # secret = request.headers.get('X-Webhook-Secret')
#     # if secret != settings.PAYMENT_WEBHOOK_SECRET:
#     #     return JsonResponse({'ok': False}, status=403)

#     order = get_object_or_404(Order, id=order_id)
#     try:
#         body = json.loads(request.body)
#     except json.JSONDecodeError:
#         return JsonResponse({"ok": False, "error": "invalid json"}, status=400)

#     new_status = body.get("payment_status")
#     if new_status in dict(Order.PAYMENT_STATUS_CHOICES):
#         order.payment_status = new_status
#         order.save(update_fields=["payment_status", "updated_at"])
#         return JsonResponse({"ok": True})

#     return JsonResponse({"ok": False, "error": "unknown status"}, status=400)


@login_required
@user_passes_test(is_manager)
@require_POST
def order_archive(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    if order.status == "delivered" and order.payment_status == "paid":
        order.is_archived = True
        order.save(update_fields=["is_archived", "updated_at"])
    # Возвращаем пустой div — карточка исчезает со страницы
    from django.http import HttpResponse

    return HttpResponse(f'<div id="order-{order.id}"></div>')


@login_required
@user_passes_test(is_manager)
def archived_orders(request):
    orders = (
        Order.objects.filter(is_archived=True)
        .select_related("user", "assigned_manager")
        .prefetch_related("items__product__images")
        .order_by("-updated_at")
    )
    return render(
        request,
        "dashboard/archived_orders.html",
        {
            "title": "Архив заказов",
            "orders": orders,
        },
    )


@login_required
@user_passes_test(is_manager)
def archive_order_card(request, order_id):
    order = get_object_or_404(
        Order.objects.select_related("user", "assigned_manager").prefetch_related(
            "items__product__images"
        ),
        id=order_id,
    )
    return render(request, "dashboard/archive_order_card.html", {"order": order})


# # поиск по артикулу


class ProductSearchView(SuperuserRequiredMixin, View):
    def get(self, request):
        query = request.GET.get("q", "").strip()
        products = []

        if query:
            starts_with = Product.objects.filter(article__istartswith=query).order_by(
                "article"
            )

            fuzzy = (
                Product.objects.exclude(article__istartswith=query)
                .annotate(similarity=TrigramSimilarity(Lower("article"), query.lower()))
                .filter(similarity__gt=0.2)
                .order_by("-similarity")
            )

            products = list(chain(starts_with, fuzzy))

        return render(
            request,
            "dashboard/product_search.html",
            {
                "products": products,
                "query": query,
            },
        )

@staff_member_required
def stock_sync(request):
    return render(request, "dashboard/stock_sync.html")


@staff_member_required
@require_http_methods(["POST"])
def stock_import(request):
    """
    Принимает .xlsx / .xls от Dropzone.
    Колонка A — name   (игнорируется)
    Колонка B — article
    Колонка C — stock
    Строка 1  — заголовок, пропускается.
    """
    uploaded = request.FILES.get("file")
    if not uploaded:
        return JsonResponse({"success": False, "error": "Файл не получен."}, status=400)

    if not uploaded.name.lower().endswith((".xlsx", ".xls")):
        return JsonResponse(
            {"success": False, "error": "Поддерживаются только .xlsx и .xls"},
            status=400,
        )

    try:
        wb = openpyxl.load_workbook(uploaded, read_only=True, data_only=True)
        ws = wb.active
    except Exception as e:
        return JsonResponse(
            {"success": False, "error": f"Не удалось открыть файл: {e}"}, status=400
        )

    updated, not_found, errors = 0, [], []

    for i, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if not row or all(v is None for v in row):
            continue
        try:
            article = (
                str(row[1]).strip() if len(row) > 1 and row[1] is not None else None
            )
            stock = row[2] if len(row) > 2 else None

            if not article:
                errors.append(f"Строка {i}: пустой артикул")
                continue
            if stock is None:
                errors.append(f"Строка {i} ({article}): пустой остаток")
                continue
            try:
                stock_value = int(float(stock))
            except (ValueError, TypeError):
                errors.append(f"Строка {i} ({article}): некорректный остаток «{stock}»")
                continue

            count = Product.objects.filter(article=article).update(stock=stock_value)
            if count:
                updated += count
            else:
                not_found.append(article)

        except Exception as e:
            errors.append(f"Строка {i}: {e}")

    wb.close()
    return JsonResponse(
        {
            "success": True,
            "updated": updated,
            "not_found": not_found,
            "not_found_count": len(not_found),
            "errors": errors,
            "errors_count": len(errors),
        }
    )


@staff_member_required
def stock_export(request):
    """Выгружает остатки всех товаров в Excel."""
    products = (
        Product.objects.all().order_by("article").values("name", "article", "stock")
    )

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Остатки"

    hdr_fill = PatternFill("solid", fgColor="0F2137")
    hdr_font = Font(bold=True, color="FFFFFF", size=11, name="Calibri")
    hdr_align = Alignment(horizontal="center", vertical="center")
    thin = Side(style="thin", color="D1D9E6")
    brd = Border(left=thin, right=thin, top=thin, bottom=thin)
    alt_fill = PatternFill("solid", fgColor="F3F6FA")

    for ci, (h, w) in enumerate(
        zip(["Наименование", "Артикул", "Остаток"], [42, 26, 12]), 1
    ):
        cell = ws.cell(row=1, column=ci, value=h)
        cell.font = hdr_font
        cell.fill = hdr_fill
        cell.alignment = hdr_align
        cell.border = brd
        ws.column_dimensions[get_column_letter(ci)].width = w
    ws.row_dimensions[1].height = 24

    for ri, p in enumerate(products, 2):
        for ci, val in enumerate(
            [p.get("name", ""), p.get("article", ""), p.get("stock", 0)], 1
        ):
            cell = ws.cell(row=ri, column=ci, value=val)
            cell.border = brd
            if ri % 2 == 0:
                cell.fill = alt_fill
            if ci == 3:
                cell.alignment = Alignment(horizontal="center")

    ws.freeze_panes = "A2"

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    response = HttpResponse(
        buf.read(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = 'attachment; filename="stock_export.xlsx"'
    return response


# Допустимые значения скидок для чекбоксов на странице (0..50 с шагом 5)
ALLOWED_DISCOUNTS = list(range(0, 51, 5))  # [0, 5, 10, ..., 50]
DEFAULT_DISCOUNTS = [0, 10, 15, 20]  # что отмечено по умолчанию в шаблоне


@staff_member_required
def price_sync(request):
    return render(
        request,
        "dashboard/price_sync.html",
        {
            "allowed_discounts": ALLOWED_DISCOUNTS,
            "default_discounts": DEFAULT_DISCOUNTS,
        },
    )


@staff_member_required
@require_http_methods(["POST"])
def price_import(request):
    """
    Принимает .xlsx / .xls от Dropzone + список выбранных скидок (чекбоксы).
    Колонка A — name         (игнорируется)
    Колонка B — article
    Колонка C — final_price  (цена на сайте)
    """
    uploaded = request.FILES.get("file")
    if not uploaded:
        return JsonResponse({"success": False, "error": "Файл не получен."}, status=400)

    if not uploaded.name.lower().endswith((".xlsx", ".xls")):
        return JsonResponse(
            {"success": False, "error": "Поддерживаются только .xlsx и .xls"},
            status=400,
        )

    # ── Получаем выбранные скидки из чекбоксов ──────────────────────────
    raw_discounts = request.POST.getlist(
        "discounts"
    )  # список строк, например ["0","10","20"]

    discounts = []
    for d in raw_discounts:
        try:
            value = int(d)
        except (ValueError, TypeError):
            continue
        if value in ALLOWED_DISCOUNTS:
            discounts.append(value)

    if not discounts:
        return JsonResponse(
            {"success": False, "error": "Выберите хотя бы один процент скидки."},
            status=400,
        )

    try:
        wb = openpyxl.load_workbook(uploaded, read_only=True, data_only=True)
        ws = wb.active
    except Exception as e:
        return JsonResponse(
            {"success": False, "error": f"Не удалось открыть файл: {e}"}, status=400
        )

    updated, not_found, errors = 0, [], []

    for i, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if not row or all(v is None for v in row):
            continue
        try:
            article = (
                str(row[1]).strip() if len(row) > 1 and row[1] is not None else None
            )
            final_price = row[2] if len(row) > 2 else None

            if not article:
                errors.append(f"Строка {i}: пустой артикул")
                continue
            if final_price is None:
                errors.append(f"Строка {i} ({article}): пустая цена")
                continue

            try:
                final_price_value = int(float(final_price))
                if final_price_value <= 0:
                    raise ValueError("цена должна быть больше нуля")
            except (ValueError, TypeError) as e:
                errors.append(
                    f"Строка {i} ({article}): некорректная цена «{final_price}» — {e}"
                )
                continue

            discount = random.choice(discounts)

            if discount == 0:
                price = final_price_value
            else:
                price = round(final_price_value / (1 - discount / 100))

            count = Product.objects.filter(article=article).update(
                price=price,
                discount_percentage=discount,
            )
            if count:
                updated += count
            else:
                not_found.append(article)

        except Exception as e:
            errors.append(f"Строка {i}: {e}")

    wb.close()
    return JsonResponse(
        {
            "success": True,
            "updated": updated,
            "not_found": not_found,
            "not_found_count": len(not_found),
            "errors": errors,
            "errors_count": len(errors),
            "discounts_used": discounts,
        }
    )


@staff_member_required
def price_export(request):
    """Выгружает name, article, final_price всех товаров в Excel."""
    products = (
        Product.objects.all()
        .order_by("article")
        .values("name", "article", "price", "discount_percentage")
    )

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Цены"

    hdr_fill = PatternFill("solid", fgColor="0F2137")
    hdr_font = Font(bold=True, color="FFFFFF", size=11, name="Calibri")
    hdr_align = Alignment(horizontal="center", vertical="center")
    thin = Side(style="thin", color="D1D9E6")
    brd = Border(left=thin, right=thin, top=thin, bottom=thin)
    alt_fill = PatternFill("solid", fgColor="F3F6FA")

    headers = ["Наименование", "Артикул", "Цена на сайте"]
    widths = [42, 26, 16]

    for ci, (h, w) in enumerate(zip(headers, widths), 1):
        cell = ws.cell(row=1, column=ci, value=h)
        cell.font = hdr_font
        cell.fill = hdr_fill
        cell.alignment = hdr_align
        cell.border = brd
        ws.column_dimensions[get_column_letter(ci)].width = w
    ws.row_dimensions[1].height = 24

    for ri, p in enumerate(products, 2):
        price = p.get("price", 0)
        discount = p.get("discount_percentage", 0)
        final_price = round(price * (100 - discount) / 100)

        row_data = [p.get("name", ""), p.get("article", ""), final_price]
        for ci, val in enumerate(row_data, 1):
            cell = ws.cell(row=ri, column=ci, value=val)
            cell.border = brd
            if ri % 2 == 0:
                cell.fill = alt_fill
            if ci == 3:
                cell.alignment = Alignment(horizontal="center")

    ws.freeze_panes = "A2"

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    response = HttpResponse(
        buf.read(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = 'attachment; filename="price_export.xlsx"'
    return response


@require_http_methods(["GET", "POST"])
def edit_start_banner(request):
    """
    Редактирование стартового баннера.
    Если его ещё нет — создаём при первом сохранении.
    """
    banner = Info.objects.filter(name="Стартовый баннер").first()

    if request.method == "POST":
        form = StartBannerForm(request.POST, request.FILES, instance=banner)
        if form.is_valid():
            form.save()
            messages.success(request, "Стартовый баннер успешно сохранён.")
            # Переходим на главную с параметром для принудительного показа баннера
            return redirect(reverse("shop:index") + "?show_banner=1")
        else:
            messages.error(request, "Пожалуйста, исправьте ошибки в форме.")
    else:
        form = StartBannerForm(instance=banner)

    return render(request, "dashboard/start_banner_form.html", {
        "form": form,
        "banner": banner,
        "page_title": "Стартовый баннер",
    })

# ── Категории и виды грибов ───────────────────────────────────────────────────
# Раздел доступен менеджерам (is_staff), т.к. справочники нужны при работе
# с товарами. Удаление блокируется, если запись используется в товарах —
# вместо удаления предлагается деактивация (is_active).


def _catalog_guard(request, obj, is_category):
    """Защита от удаления используемого справочника.

    Если к записи привязаны товары — удаление отменяется, администратору
    предлагается деактивировать запись. Возвращает True, если удалено.
    """
    related = obj.products.count()
    if related:
        kind = "категорию" if is_category else "вид гриба"
        messages.error(
            request,
            f"Нельзя удалить {kind} «{obj.name}»: привязано товаров — {related}. "
            f"Снимите галочку «Показывать на сайте», чтобы скрыть его из витрины.",
        )
        return False
    obj.delete()
    messages.success(request, f"«{obj.name}» удалён.")
    return True


@login_required
@user_passes_test(is_manager)
def category_list(request):
    query = request.GET.get("q", "").strip()
    categories = Category.objects.all().order_by("name")
    if query:
        categories = categories.filter(name__icontains=query)
    categories = categories.annotate(products_count=db_models.Count("products"))

    return render(
        request,
        "dashboard/category_list.html",
        {
            "title": "Категории",
            "categories": categories,
            "query": query,
            "total": Category.objects.count(),
        },
    )


@login_required
@user_passes_test(is_manager)
def category_create(request):
    if request.method == "POST":
        form = CategoryForm(request.POST, request.FILES)
        if form.is_valid():
            category = form.save()
            messages.success(request, f"Категория «{category.name}» создана.")
            return redirect("dashboard:category_list")
        messages.error(request, "Пожалуйста, исправьте ошибки в форме.")
    else:
        form = CategoryForm()

    return render(
        request,
        "dashboard/category_form.html",
        {
            "form": form,
            "title": "Новая категория",
            "is_edit": False,
            "back_url": reverse("dashboard:category_list"),
        },
    )


@login_required
@user_passes_test(is_manager)
def category_edit(request, pk):
    category = get_object_or_404(Category, pk=pk)

    if request.method == "POST":
        form = CategoryForm(request.POST, request.FILES, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, f"Категория «{category.name}» сохранена.")
            return redirect("dashboard:category_list")
        messages.error(request, "Пожалуйста, исправьте ошибки в форме.")
    else:
        form = CategoryForm(instance=category)

    return render(
        request,
        "dashboard/category_form.html",
        {
            "form": form,
            "title": f"Категория: {category.name}",
            "is_edit": True,
            "category": category,
            "products_count": category.products.count(),
            "back_url": reverse("dashboard:category_list"),
        },
    )


@login_required
@user_passes_test(is_manager)
@require_POST
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk)
    _catalog_guard(request, category, is_category=True)
    return redirect("dashboard:category_list")


@login_required
@user_passes_test(is_manager)
def category_toggle(request, pk):
    """Быстрое включение/выключение категории прямо из списка."""
    category = get_object_or_404(Category, pk=pk)
    category.is_active = not category.is_active
    category.save(update_fields=["is_active", "updated_at"])
    state = "показана на сайте" if category.is_active else "скрыта с сайта"
    messages.success(request, f"Категория «{category.name}» {state}.")
    return redirect("dashboard:category_list")


@login_required
@user_passes_test(is_manager)
def mushroom_type_list(request):
    query = request.GET.get("q", "").strip()
    mushroom_types = MushroomType.objects.all().order_by("name")
    if query:
        mushroom_types = mushroom_types.filter(name__icontains=query)
    mushroom_types = mushroom_types.annotate(
        products_count=db_models.Count("products")
    )

    return render(
        request,
        "dashboard/mushroom_type_list.html",
        {
            "title": "Виды грибов",
            "mushroom_types": mushroom_types,
            "query": query,
            "total": MushroomType.objects.count(),
        },
    )


@login_required
@user_passes_test(is_manager)
def mushroom_type_create(request):
    if request.method == "POST":
        form = MushroomTypeForm(request.POST, request.FILES)
        if form.is_valid():
            mushroom_type = form.save()
            messages.success(request, f"Вид гриба «{mushroom_type.name}» создан.")
            return redirect("dashboard:mushroom_type_list")
        messages.error(request, "Пожалуйста, исправьте ошибки в форме.")
    else:
        form = MushroomTypeForm()

    return render(
        request,
        "dashboard/mushroom_type_form.html",
        {
            "form": form,
            "title": "Новый вид гриба",
            "is_edit": False,
            "back_url": reverse("dashboard:mushroom_type_list"),
        },
    )


@login_required
@user_passes_test(is_manager)
def mushroom_type_edit(request, pk):
    mushroom_type = get_object_or_404(MushroomType, pk=pk)

    if request.method == "POST":
        form = MushroomTypeForm(request.POST, request.FILES, instance=mushroom_type)
        if form.is_valid():
            form.save()
            messages.success(request, f"Вид гриба «{mushroom_type.name}» сохранён.")
            return redirect("dashboard:mushroom_type_list")
        messages.error(request, "Пожалуйста, исправьте ошибки в форме.")
    else:
        form = MushroomTypeForm(instance=mushroom_type)

    return render(
        request,
        "dashboard/mushroom_type_form.html",
        {
            "form": form,
            "title": f"Вид гриба: {mushroom_type.name}",
            "is_edit": True,
            "mushroom_type": mushroom_type,
            "products_count": mushroom_type.products.count(),
            "back_url": reverse("dashboard:mushroom_type_list"),
        },
    )


@login_required
@user_passes_test(is_manager)
@require_POST
def mushroom_type_delete(request, pk):
    mushroom_type = get_object_or_404(MushroomType, pk=pk)
    _catalog_guard(request, mushroom_type, is_category=False)
    return redirect("dashboard:mushroom_type_list")


@login_required
@user_passes_test(is_manager)
def mushroom_type_toggle(request, pk):
    """Быстрое включение/выключение вида гриба прямо из списка."""
    mushroom_type = get_object_or_404(MushroomType, pk=pk)
    mushroom_type.is_active = not mushroom_type.is_active
    mushroom_type.save(update_fields=["is_active"])
    state = "показан на сайте" if mushroom_type.is_active else "скрыт с сайта"
    messages.success(request, f"Вид гриба «{mushroom_type.name}» {state}.")
    return redirect("dashboard:mushroom_type_list")
