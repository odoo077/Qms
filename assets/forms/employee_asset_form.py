# assets/forms/employee_asset_form.py
from django import forms
from django.db.models import Q
from django.utils import timezone

from assets.models import EmployeeAsset, AssetItem
from .base import TailwindFormMixin, CompanyScopedFormMixin

# ---------- 1) نموذج إنشاء/تسليم أصل ----------
class EmployeeAssetAssignForm(CompanyScopedFormMixin, TailwindFormMixin, forms.ModelForm):
    """
    تسليم أصل لموظف (ينشئ سجل EmployeeAsset جديد).
    - نفلتر العناصر: الشركة الحالية + غير مفقودة/خردة + غير مسلمة حاليًا.
    """
    class Meta:
        model = EmployeeAsset
        fields = [
            "employee",
            "item",
            "date_assigned",
            "due_back",
            "handover_note",
        ]
        widgets = {
            "handover_note": forms.Textarea(attrs={"rows": 3}),
            "date_assigned": forms.DateInput(),
            "due_back": forms.DateInput(),
        }

    def __init__(self, *args, **kwargs):
        # يمكن تمرير employee مسبقًا لإخفائه/تثبيته
        fixed_employee = kwargs.pop("employee", None)
        super().__init__(*args, **kwargs)

        # employee و item يجب أن يطابقا الشركة
        if self.company:
            self.fields["employee"].queryset = self.fields["employee"].queryset.filter(
                company=self.company, active=True
            ).order_by("name")

            busy_items = EmployeeAsset.objects.filter(is_active=True).values_list("item_id", flat=True)
            self.fields["item"].queryset = AssetItem.objects.filter(
                company=self.company,
                active=True,
            ).exclude(
                Q(status__in=["lost", "scrapped"]) | Q(pk__in=busy_items)
            ).select_related("model", "model__type").order_by("model__type__name", "model__name", "asset_tag")

        if fixed_employee:
            self.fields["employee"].initial = fixed_employee
            self.fields["employee"].disabled = True

        # افتراضي: اليوم
        self.fields["date_assigned"].initial = timezone.now().date()

    def clean(self):
        cleaned = super().clean()
        emp = cleaned.get("employee")
        item = cleaned.get("item")

        if emp and item and emp.company_id != item.company_id:
            self.add_error("item", "Item company must match employee company.")
        return cleaned


# ---------- 2) نموذج إرجاع أصل ----------
class EmployeeAssetReturnForm(TailwindFormMixin, forms.ModelForm):
    class Meta:
        model = EmployeeAsset
        fields = ["date_returned", "return_note"]
        widgets = {
            "date_returned": forms.DateInput(),
            "return_note": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["date_returned"].initial = timezone.now().date()


# ---------- 3) نموذج تحويل أصل ----------
class EmployeeAssetTransferForm(CompanyScopedFormMixin, TailwindFormMixin, forms.Form):
    """
    تحويل أصل مسلّم من موظف إلى آخر.
    يُستخدم مع Service.transfer_item في الـ View.
    """
    to_employee = forms.ModelChoiceField(queryset=None)
    date_assigned = forms.DateField(required=False)
    due_back = forms.DateField(required=False)
    note = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, **kwargs):
        # نتوقع تمرير item من الـ View
        self.item = kwargs.pop("item", None)
        super().__init__(*args, **kwargs)
        if self.company:
            self.fields["to_employee"].queryset = self.fields["to_employee"].queryset.filter(
                company=self.company, active=True
            ).order_by("name")
        self.fields["date_assigned"].initial = timezone.now().date()

    def clean(self):
        cleaned = super().clean()
        emp = cleaned.get("to_employee")
        if self.item and emp and self.item.company_id != emp.company_id:
            self.add_error("to_employee", "Employee company must match item company.")
        return cleaned
