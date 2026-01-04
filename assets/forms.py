# assets/forms.py
from __future__ import annotations

from datetime import date
from typing import Optional

from django import forms
from django.apps import apps

from base.company_context import get_company_id as get_current_company
from base.models import Company

from . import models as m


# ============================================================
#  Base Scoped Form (Odoo-style filtering)
# ============================================================

class ScopedModelForm(forms.ModelForm):
    """
    Base reusable form that:
      - Receives request for company context scoping.
      - Filters FK fields by company.
      - Sets default company on creation when possible.
    """

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

        company_field = self.fields.get("company")
        if company_field:
            allowed_companies = Company.objects.with_acl("view")
            company_field.queryset = allowed_companies

            cur_id = get_current_company(self.request)
            if cur_id and allowed_companies.filter(pk=cur_id).exists():
                if not getattr(self.instance, "pk", None):
                    company_field.initial = cur_id

    def _current_company_id_for_filtering(self):
        company_id = None

        if "company" in self.fields:
            company_id = (
                self.data.get(self.add_prefix("company"))
                or self.initial.get("company")
                or getattr(self.instance, "company_id", None)
            )

        if not company_id:
            company_id = get_current_company(self.request)

        return company_id

    def _filter_by_company(self, field_name: str, qs, *, active_only: bool = False):
        if field_name not in self.fields:
            return

        company_id = self._current_company_id_for_filtering()

        if active_only and hasattr(qs.model, "active"):
            qs = qs.filter(active=True)

        if company_id:
            self.fields[field_name].queryset = qs.filter(company_id=company_id)
        else:
            allowed_ids = Company.objects.with_acl("view").values_list("id", flat=True)
            self.fields[field_name].queryset = qs.filter(company_id__in=allowed_ids)

    def _exclude_self(self, field_name: str):
        if field_name not in self.fields:
            return
        if getattr(self.instance, "pk", None):
            self.fields[field_name].queryset = self.fields[field_name].queryset.exclude(pk=self.instance.pk)


# ============================================================
#  Category Form
# ============================================================

class AssetCategoryForm(ScopedModelForm):
    class Meta:
        model = m.AssetCategory
        fields = ["name", "company", "parent", "active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._filter_by_company("parent", m.AssetCategory.objects.all(), active_only=False)
        self._exclude_self("parent")

        if self.instance.pk and "company" in self.fields:
            self.fields["company"].disabled = True


# ============================================================
#  Asset Form
# ============================================================

class AssetForm(ScopedModelForm):
    class Meta:
        model = m.Asset
        fields = [
            "name",
            "code",
            "serial",
            "company",
            "category",
            "department",
            "status",
            "purchase_date",
            "purchase_value",
            "note",
            "parent",
            "active",
        ]
        # holder ليس حقل UI عام لأنه يُدار عبر Workflow (Assign/Unassign)
        # وسيظهر read-only في التفاصيل فقط لاحقًا

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._filter_by_company("category", m.AssetCategory.objects.all(), active_only=True)

        Department = apps.get_model("hr", "Department")
        self._filter_by_company("department", Department.objects.all(), active_only=True)

        self._filter_by_company("parent", m.Asset.objects.all(), active_only=True)
        self._exclude_self("parent")

        if self.instance.pk and "company" in self.fields:
            self.fields["company"].disabled = True


# ============================================================
#  Workflow Forms (Assign / Unassign)
# ============================================================

class AssetAssignForm(forms.Form):
    """
    Workflow: Assign Asset to Employee (calls services.assign_asset)
    """
    employee = forms.ModelChoiceField(queryset=apps.get_model("hr", "Employee").objects.none())
    date_from = forms.DateField(required=False, initial=date.today)
    note = forms.CharField(required=False, max_length=255)

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        self.asset: m.Asset = kwargs.pop("asset")

        # ✅ NEW (إضافة)
        self.assign_to_employee_id = kwargs.pop("assign_to_employee_id", None)

        super().__init__(*args, **kwargs)

        Employee = apps.get_model("hr", "Employee")

        qs = Employee.objects.all()
        if hasattr(Employee, "active"):
            qs = qs.filter(active=True)
        if getattr(Employee, "company_id", None) is not None:
            qs = qs.filter(company_id=self.asset.company_id)

        self.fields["employee"].queryset = qs

        # ==================================================
        # ✅ NEW: Auto-select employee when coming from Employee page
        # ==================================================
        if self.assign_to_employee_id:
            try:
                employee = qs.get(pk=self.assign_to_employee_id)
                self.fields["employee"].initial = employee
                self.fields["employee"].disabled = True
            except Employee.DoesNotExist:
                pass


class AssetUnassignForm(forms.Form):
    """
    Workflow: Unassign Asset (calls services.unassign_asset)
    """
    date_to = forms.DateField(required=False, initial=date.today)
    note = forms.CharField(required=False, max_length=255)

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        self.asset: m.Asset = kwargs.pop("asset")
        super().__init__(*args, **kwargs)

