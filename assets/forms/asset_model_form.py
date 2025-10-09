# assets/forms/asset_model_form.py
from django import forms
from assets.models import AssetModel, AssetType
from .base import TailwindFormMixin

class AssetModelForm(TailwindFormMixin, forms.ModelForm):
    class Meta:
        model = AssetModel
        fields = [
            "active",
            "type",
            "name",
            "manufacturer",
            "sku",
            "specifications",
            "sequence",
            "color",
            "image",
            "notes",
        ]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # نعرض فقط أنواع فعّالة
        self.fields["type"].queryset = AssetType.objects.filter(active=True).order_by("name")

    def clean(self):
        cleaned = super().clean()
        # مسح white-spaces
        for k in ("name", "manufacturer", "sku"):
            if cleaned.get(k):
                cleaned[k] = cleaned[k].strip()
        return cleaned
