from django import forms
from .models import Category, MushroomType


class ProductFilterForm(forms.Form):
    category = forms.ModelChoiceField(
        queryset=Category.objects.filter(is_active=True),
        label="Категория",
        required=False,
        empty_label="Все категории",
        widget=forms.Select(attrs={
            "hx-get": "",  # заполним в шаблоне через url-тег, см. ниже
            "hx-trigger": "change",
            "hx-target": "#catalog-results",
            "hx-swap": "innerHTML",
            "hx-push-url": "true",
            "hx-include": "#filter-form",
        }),
    )
    mushroom_types = forms.ModelMultipleChoiceField(
        label="Виды грибов",
        queryset=MushroomType.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    price_max = forms.IntegerField(
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={"type": "range"}),
    )