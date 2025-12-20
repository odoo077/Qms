# assets/forms.py
from __future__ import annotations

from django import forms
from django.apps import apps

from base.company_context import get_company_id as get_current_company
from base.models import Company

from . import models as m


# ============================================================
#  Base Scoped Form (Odoo-style filtering)
# ============================================================

class _ScopedModelForm(forms.ModelForm):
    """
    Base reusable form that:
      - Receives request for company & ACL scoping.
      - Filters foreign-key fields by active/allowed companies.
      - Automatically sets default company on creation.
    """

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

        # -------- 1) Filter "company" field by what the user can see --------
        company_field = self.fields.get("company")
        if company_field:
            allowed_companies = Company.objects.with_acl("view")
            company_field.queryset = allowed_companies

            # -------- 2) Set default company for new records --------
            cur_id = get_current_company(self.request)
            if cur_id and allowed_companies.filter(pk=cur_id).exists():
                if not getattr(self.instance, "pk", None):
                    company_field.initial = cur_id

    # ------------------------------------
    # Helper: detect company_id for filtering
    # ------------------------------------
    def _current_company_id_for_filtering(self):
        """
        Resolve company_id from:
          1) posted data (company field)
          2) initial
          3) instance.company_id
          4) request current company context
        """
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

    # ------------------------------------
    # Helper: Filter related FKs by company
    # ------------------------------------
    def _filter_by_company(self, field_name: str, qs, *, active_only: bool = False):
        """
        Filter FK field queryset by resolved company_id.
        If company_id is not resolvable, fallback to companies visible by ACL(view).
        """
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
        """
        If field points to same model (parent relation), exclude self to prevent self-parent selection.
        """
        if field_name not in self.fields:
            return
        if getattr(self.instance, "pk", None):
            self.fields[field_name].queryset = self.fields[field_name].queryset.exclude(pk=self.instance.pk)


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
        self._filter_by_company("parent", m.AssetCategory.objects.all(), active_only=False)
        self._exclude_self("parent")

        # OPTIONAL: when editing, prevent company change (Odoo-like)
        if self.instance.pk and "company" in self.fields:
            self.fields["company"].disabled = True


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

        # Category filtered by company (prefer active categories only)
        self._filter_by_company("category", m.AssetCategory.objects.all(), active_only=True)

        # HR-related fields (department / holder) — resolved lazily (avoid import-order issues)
        Department = apps.get_model("hr", "Department")
        Employee = apps.get_model("hr", "Employee")

        self._filter_by_company("department", Department.objects.all(), active_only=True)
        self._filter_by_company("holder", Employee.objects.all(), active_only=True)

        # Parent asset (same company, active only)
        self._filter_by_company("parent", m.Asset.objects.all(), active_only=True)
        self._exclude_self("parent")

        # OPTIONAL: when editing, prevent company change (like Odoo)
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

        # Assets filtered by company (active only)
        self._filter_by_company("asset", m.Asset.objects.all(), active_only=True)

        # Employee filtered by company (active only) — resolved lazily
        Employee = apps.get_model("hr", "Employee")
        self._filter_by_company("employee", Employee.objects.all(), active_only=True)

        # OPTIONAL: when editing, prevent company change (Odoo-like behavior)
        if self.instance.pk and "company" in self.fields:
            self.fields["company"].disabled = True
