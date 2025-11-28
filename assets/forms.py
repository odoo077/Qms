# assets/forms.py
from __future__ import annotations
from typing import Any, Dict

from django import forms
from django.contrib.auth import get_user_model

from base.company_context import get_company_id as get_current_company
from base.models import Company
from base.acl_service import has_perm
from . import models as m

User = get_user_model()


# ============================================================
#  Base Scoped Form (Odoo-style filtering)
# ============================================================

class _ScopedModelForm(forms.ModelForm):
    """
    Base reusable form that:
      - Receives request for company & ACL scoping.
      - Filters foreign-key fields by active companies.
      - Automatically sets default company on creation.
    """

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

        # -------- 1) Filter "company" field by what the user can see --------
        allowed_companies = Company.objects.with_acl("view")
        company_field = self.fields.get("company")
        if company_field:
            company_field.queryset = allowed_companies

        # -------- 2) Set default company for new records --------
        cur_id = get_current_company(self.request)
        if cur_id and company_field and allowed_companies.filter(pk=cur_id).exists():
            if not getattr(self.instance, "pk", None):
                self.fields["company"].initial = cur_id

    # ------------------------------------
    # Helper: Filter related FKs by company
    # ------------------------------------
    def _filter_by_company(self, field_name: str, qs):
        if field_name not in self.fields:
            return

        # Company for filtering
        company_id = None

        if "company" in self.fields:
            company_id = (
                self.data.get(self.add_prefix("company"))
                or self.initial.get("company")
                or getattr(self.instance, "company_id", None)
            )

        if company_id:
            self.fields[field_name].queryset = qs.filter(company_id=company_id)
        else:
            # fallback: any company the user can see
            self.fields[field_name].queryset = qs.filter(
                company_id__in=Company.objects.with_acl("view").values("id")
            )


# ============================================================
#  Category Form
# ============================================================

class AssetCategoryForm(_ScopedModelForm):
    class Meta:
        model = m.AssetCategory
        fields = ["name", "company", "parent", "active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Parent category must belong to same company
        self._filter_by_company("parent", m.AssetCategory.objects.all())


# ============================================================
#  Asset Form
# ============================================================

class AssetForm(_ScopedModelForm):
    class Meta:
        model = m.Asset
        fields = [
            "name",
            "code",
            "serial",
            "company",
            "category",
            "department",
            "holder",
            "status",
            "purchase_date",
            "purchase_value",
            "note",
            "parent",
            "active",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Category filtered by company
        self._filter_by_company("category", m.AssetCategory.objects.all())

        # HR-related fields (department / holder)
        from hr.models import Department, Employee
        self._filter_by_company("department", Department.objects.all())
        self._filter_by_company("holder", Employee.objects.all())

        # Parent asset (same company)
        self._filter_by_company("parent", m.Asset.objects.all())

        # OPTIONAL PROTECTION:
        # When editing, prevent company change (like Odoo)
        if self.instance.pk and "company" in self.fields:
            self.fields["company"].disabled = True


# ============================================================
#  Assignment Form
# ============================================================

class AssetAssignmentForm(_ScopedModelForm):
    class Meta:
        model = m.AssetAssignment
        fields = [
            "asset",
            "employee",
            "company",
            "date_from",
            "date_to",
            "note",
            "active",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Assets filtered by company
        self._filter_by_company("asset", m.Asset.objects.all())

        # Employee filtered by company
        from hr.models import Employee
        self._filter_by_company("employee", Employee.objects.all())

        # Protect company once created (Odoo-like behavior)
        if self.instance.pk and "company" in self.fields:
            self.fields["company"].disabled = True
