from django import forms
from .models import Category, MushroomType


class ProductFilterForm(forms.Form):
    category = forms.ModelChoiceField(
        queryset=Category.objects.filter(is_active=True),
        label="Категория",
        required=False,
        empty_label="Все категории",
        widget=forms.Select(
            attrs={
                "hx-get": "",  # заполним в шаблоне через url-тег, см. ниже
                "hx-trigger": "change",
                "hx-target": "#catalog-results",
                "hx-swap": "innerHTML",
                "hx-push-url": "true",
                "hx-include": "#filter-form",
            }
        ),
    )
    mushroom_types = forms.ModelMultipleChoiceField(
        label="Виды грибов",
        queryset=MushroomType.objects.filter(is_active=True),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    price_max = forms.IntegerField(
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={"type": "range"}),
    )
    weight_max = forms.IntegerField(
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={"type": "range"}),
    )


class OrderForm(forms.Form):
    first_name = forms.CharField(
        label="Имя",
        max_length=100,
        widget=forms.TextInput(attrs={"placeholder": "Мария"}),
    )
    last_name = forms.CharField(
        label="Фамилия",
        max_length=100,
        widget=forms.TextInput(attrs={"placeholder": "Иванова"}),
    )
    customer_email = forms.EmailField(
        label="Email", widget=forms.EmailInput(attrs={"placeholder": "example@mail.ru"})
    )
    customer_phone = forms.CharField(
        label="Телефон",
        max_length=20,
        widget=forms.TextInput(attrs={"placeholder": "+7 (999) 123-45-67"}),
    )
    delivery_city = forms.CharField(
        label="Город",
        max_length=100,
        widget=forms.TextInput(attrs={"placeholder": "Новосибирск"}),
    )
    delivery_address = forms.CharField(
        label="Адрес доставки",
        max_length=255,
        widget=forms.TextInput(attrs={"placeholder": "ул. Ленина, д. 1, кв. 10"}),
    )
    delivery_postal_code = forms.CharField(
        label="Индекс",
        max_length=20,
        widget=forms.TextInput(attrs={"placeholder": "630000"}),
    )
    notes = forms.CharField(
        label="Комментарий к заказу",
        required=False,
        widget=forms.Textarea(
            attrs={"rows": 3, "placeholder": "Позвонить за час до доставки..."}
        ),
    )

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Поля профиля и откуда их брать
        profile_fields = {
            "first_name": getattr(user, "first_name", ""),
            "last_name": getattr(user, "last_name", ""),
            "customer_email": getattr(user, "email", ""),
            "customer_phone": getattr(user, "phone_number", ""),
            "delivery_city": getattr(user, "delivery_city", ""),
            "delivery_address": getattr(user, "delivery_address", ""),
            "delivery_postal_code": getattr(user, "delivery_postal_code", ""),
        }

        for field_name, value in profile_fields.items():
            if value:
                self.fields[field_name].initial = value

        required_fields = {
            "first_name",
            "last_name",
            "customer_email",
            "customer_phone",
            "delivery_city",
            "delivery_address",
            "delivery_postal_code",
        }
        for name, field in self.fields.items():
            if name not in required_fields:
                field.required = False


class ReviewForm(forms.Form):
    rating = forms.IntegerField(
        label="Оценка",
        min_value=1,
        max_value=5,
        widget=forms.NumberInput(
            attrs={"type": "range", "min": 1, "max": 5, "step": 1}
        ),
    )
    title = forms.CharField(
        label="Заголовок",
        max_length=200,
        widget=forms.TextInput(attrs={"placeholder": "Кратко о товаре"}),
    )
    author_name = forms.CharField(
        required=False,
    )

    advantages = forms.CharField(
        label="Достоинства",
        required=False,
        widget=forms.Textarea(
            attrs={"rows": 4, "placeholder": "Что вам понравилось..."}
        ),
    )

    disadvantages = forms.CharField(
        label="Недостатки",
        required=False,
        widget=forms.Textarea(
            attrs={"rows": 4, "placeholder": "Что не понравилось..."}
        ),
    )

    text = forms.CharField(
        required=False,
        label="Текст отзыва",
        widget=forms.Textarea(
            attrs={"rows": 4, "placeholder": "Поделитесь впечатлениями..."}
        ),
    )
