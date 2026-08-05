from django import forms

from shop.models import  Product


# class OrderStatusForm(forms.ModelForm):
#     class Meta:
#         model = Order
#         fields = ["status"]


# class OrderShipForm(forms.ModelForm):
#     """Отдельная форма для отправки — там ещё трек-номер"""

#     class Meta:
#         model = Order
#         fields = ["tracking_number"]


# class OrderPaymentStatusForm(forms.ModelForm):
#     class Meta:
#         model = Order
#         fields = ["payment_status"]


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            "name",
            "article",
            "category",
            "is_set",
            "mushroom_types",
            "price",
            "discount_percentage",
            "stock",
            "out_of_stock_behavior",
            "description",
            "ingredients",
            "preservation_method",
            "release_form",
            "country_of_origin",
            "nutrition_fat",
            "nutrition_protein",
            "nutrition_carbs",
            "nutrition_calories",
            "is_gmo_free",
            "is_vegetarian",
            "storage_temp_min",
            "storage_temp_max",
            "shelf_life_months",
            "net_weight",
            "kit",
            "package",
            "packaging_weight",
            "total_weight",
            "packaging_length",
            "packaging_width",
            "packaging_height",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "ingredients": forms.Textarea(attrs={"rows": 3}),
            "out_of_stock_behavior": forms.Select(attrs={"class": "form-control"}),
            "preservation_method": forms.Select(attrs={"class": "form-control"}),
            "release_form": forms.Select(attrs={"class": "form-control"}),
            "mushroom_types": forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Обязательные — как и раньше, только базовый минимум
        required_fields = {"name", "article", "category", "price"}
        for name, field in self.fields.items():
            if name not in required_fields:
                field.required = False
            # mushroom_types рендерим чекбоксами вручную в шаблоне —
            # класс form-control ему не нужен
            if name != "mushroom_types":
                field.widget.attrs.setdefault("class", "form-control")

    def clean(self):
        cleaned_data = super().clean()
        is_set = cleaned_data.get("is_set")
        mushroom_types = cleaned_data.get("mushroom_types")
        # Переносим сюда ту же проверку, что в Product.clean(),
        # чтобы пользователь увидел ошибку прямо в форме, а не при save()
        if not is_set and mushroom_types and mushroom_types.count() > 1:
            self.add_error(
                "mushroom_types",
                "Товар с несколькими видами грибов должен быть отмечен как «Ассорти/набор»",
            )
        return cleaned_data

# class ProductHairLengthForm(forms.Form):
#     product_id = forms.IntegerField(widget=forms.HiddenInput())
#     hair_length = forms.IntegerField(
#         required=True,
#         min_value=0,
#         widget=forms.NumberInput(
#             attrs={"class": "form-control", "placeholder": "Введите длину волос"}
#         ),
#     )
