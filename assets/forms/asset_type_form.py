# assets/forms/asset_type_form.py
from django import forms
from assets.models import AssetType
from .base import TailwindFormMixin

class AssetTypeForm(TailwindFormMixin, forms.ModelForm):
    class Meta:
        model = AssetType
        fields = [
            "active",          # من ActivableMixin
            "name",
            "code",
            "default_warranty_months",
            "icon",
            "description",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def clean_default_warranty_months(self):
        val = self.cleaned_data.get("default_warranty_months") or 0
        if val < 0:
            raise forms.ValidationError("Warranty months cannot be negative.")
        return val

    def clean_code(self):
        code = (self.cleaned_data.get("code") or "").strip().lower()
        if not code:
            raise forms.ValidationError("Code is required.")
        return code
