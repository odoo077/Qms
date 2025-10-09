# assets/forms/asset_item_form.py
from django import forms
from django.utils import timezone
from assets.models import AssetItem, AssetModel
from .base import TailwindFormMixin, CompanyScopedFormMixin

class AssetItemForm(CompanyScopedFormMixin, TailwindFormMixin, forms.ModelForm):
    """
    إنشاء/تعديل أصل ملموس. الشركة تأتي من CompanyOwnedMixin داخل الموديل
    لكننا نستخدم company لفلترة القوائم المساعدة فقط.
    """
    class Meta:
        model = AssetItem
        fields = [
            "active",
            "company",            # CompanyOwnedMixin
            "model",
            "asset_tag",
            "serial_no",
            "status",
            "purchase_date",
            "purchase_cost",
            "warranty_months",
            "warranty_expiry",    # محسوب/مخزّن؛ نسمح بتعديله يدويًا إن رغبت
            "location",
            "notes",
        ]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
            "purchase_date": forms.DateInput(),
            "warranty_expiry": forms.DateInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # نموذج/طراز فعّال فقط
        self.fields["model"].queryset = AssetModel.objects.filter(active=True).select_related("type").order_by(
            "type__name", "name"
        )

        # لو تم تمرير الشركة في kwargs، ثبّتها واجعلها للقراءة فقط (اختياري)
        if self.company:
            self.fields["company"].initial = self.company
            self.fields["company"].disabled = True

    def clean(self):
        cleaned = super().clean()
        # ضمان أن warranty_expiry ≥ purchase_date (إن تم إدخاله يدويًا)
        pd = cleaned.get("purchase_date")
        we = cleaned.get("warranty_expiry")
        if pd and we and we < pd:
            self.add_error("warranty_expiry", "Warranty expiry cannot be before purchase date.")
        return cleaned
