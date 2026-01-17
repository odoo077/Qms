# assets/forms.py
from __future__ import annotations

from datetime import date
from typing import Optional

from django import forms
from django.apps import apps

from base.company_context import get_company_id as get_current_company
from base.models import Company
from django.utils.translation import gettext_lazy as _
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
            allowed_companies = Company.objects.all()
            company_field.queryset = allowed_companies

            cur_id = get_current_company(self.request)
            if cur_id and allowed_companies.filter(pk=cur_id).exists():
                if not getattr(self.instance, "pk", None):
                    company_field.initial = cur_id

    def _current_company_id_for_filtering(self) -> Optional[int]:
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
            self.fields[field_name].queryset = qs.none()

    def _exclude_self(self, field_name: str):
        if field_name not in self.fields:
            return
        if getattr(self.instance, "pk", None):
            self.fields[field_name].queryset = (
                self.fields[field_name].queryset.exclude(pk=self.instance.pk)
            )


# ============================================================
#  Category Form
# ============================================================




class AssetCategoryForm(ScopedModelForm):
    """
    Asset Category Form (Production-grade)

    Rules:
    - Company is set once and locked on update
    - Parent category:
        * Same company only
        * Can include inactive (for re-parenting)
        * Cannot be self
    - Clean, minimal, explicit fields
    """

    class Meta:
        model = m.AssetCategory
        fields = [
            "name",
            "company",
            "parent",
            "active",
        ]
        widgets = {
            "name": forms.TextInput(attrs={
                "class": "input input-bordered w-full",
                "placeholder": _("e.g. IT Equipment, Vehicles"),
            }),
            "company": forms.Select(attrs={
                "class": "select select-bordered w-full",
            }),
            "parent": forms.Select(attrs={
                "class": "select select-bordered w-full",
            }),
            "active": forms.CheckboxInput(attrs={
                "class": "checkbox checkbox-sm",
            }),
        }
        help_texts = {
            "name": _("Clear and unique name within the same company."),
            "parent": _("Optional. Used to build category hierarchy."),
            "active": _("Inactive categories are hidden but not deleted."),
        }

    # --------------------------------------------------
    # Initialization
    # --------------------------------------------------
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # ----------------------------------------------
        # Parent category:
        # - Same company only
        # - Include inactive (best practice for hierarchy edits)
        # ----------------------------------------------
        self._filter_by_company(
            "parent",
            m.AssetCategory.objects.all(),
            active_only=False,
        )

        # Prevent selecting self as parent (UX layer)
        self._exclude_self("parent")

        # ----------------------------------------------
        # Company field rules
        # ----------------------------------------------
        if self.instance.pk:
            # Company is structural → lock on edit
            if "company" in self.fields:
                self.fields["company"].disabled = True
        else:
            # On create: company is required UX-wise
            if "company" in self.fields:
                self.fields["company"].required = True

    # --------------------------------------------------
    # Validation
    # --------------------------------------------------
    def clean_name(self):
        name = (self.cleaned_data.get("name") or "").strip()
        if not name:
            raise forms.ValidationError(_("Category name cannot be empty."))
        return name

    def clean(self):
        """
        Extra defensive validation (human-friendly).
        Model-level constraints already exist; this improves UX.
        """
        cleaned = super().clean()

        company = cleaned.get("company")
        parent = cleaned.get("parent")

        if parent and company and parent.company_id != company.id:
            self.add_error(
                "parent",
                _("Parent category must belong to the same company.")
            )

        return cleaned



# ============================================================
#  Asset Form
# ============================================================


class AssetForm(ScopedModelForm):
    """
    Asset Form (Production-grade)

    Principles (Odoo-like strict):
    - holder is NOT managed here (Assign/Unassign workflow only)
    - status cannot be set to ASSIGNED from this form
    - category/department/parent filtered by company
    - company locked on update
    """

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
        widgets = {
            "name": forms.TextInput(attrs={
                "class": "input input-bordered w-full",
                "placeholder": _("e.g. Laptop Dell Latitude"),
            }),
            "code": forms.TextInput(attrs={
                "class": "input input-bordered w-full",
                "placeholder": _("Unique code per company"),
                "autocomplete": "off",
            }),
            "serial": forms.TextInput(attrs={
                "class": "input input-bordered w-full",
                "placeholder": _("Optional serial number"),
                "autocomplete": "off",
            }),
            "company": forms.Select(attrs={
                "class": "select select-bordered w-full",
            }),
            "category": forms.Select(attrs={
                "class": "select select-bordered w-full",
            }),
            "department": forms.Select(attrs={
                "class": "select select-bordered w-full",
            }),
            "status": forms.Select(attrs={
                "class": "select select-bordered w-full",
            }),
            "purchase_date": forms.DateInput(attrs={
                "class": "input input-bordered w-full",
                "type": "date",
            }),
            "purchase_value": forms.NumberInput(attrs={
                "class": "input input-bordered w-full",
                "step": "0.01",
                "min": "0",
                "placeholder": _("0.00"),
            }),
            "note": forms.Textarea(attrs={
                "class": "textarea textarea-bordered w-full",
                "rows": 4,
                "placeholder": _("Optional notes..."),
            }),
            "parent": forms.Select(attrs={
                "class": "select select-bordered w-full",
            }),
            "active": forms.CheckboxInput(attrs={
                "class": "checkbox checkbox-sm",
            }),
        }
        help_texts = {
            "code": _("Must be unique within the same company."),
            "serial": _("Optional. If provided, must be unique within the same company."),
            "category": _("Only categories from the selected company are shown."),
            "department": _("Only departments from the selected company are shown."),
            "status": _("Assignment status is managed via Assign/Unassign workflow."),
            "parent": _("Optional. Use to build parent/child asset structure."),
            "active": _("Inactive assets are hidden but not deleted."),
        }

    # --------------------------------------------------
    # Initialization
    # --------------------------------------------------
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # ----------------------------------------------
        # Company rules
        # ----------------------------------------------
        if self.instance.pk and "company" in self.fields:
            self.fields["company"].disabled = True
        else:
            if "company" in self.fields:
                self.fields["company"].required = True

        # ----------------------------------------------
        # Filter related fields by company scope
        # ----------------------------------------------
        self._filter_by_company(
            "category",
            m.AssetCategory.objects.all(),
            active_only=True,
        )

        Department = apps.get_model("hr", "Department")
        self._filter_by_company(
            "department",
            Department.objects.all(),
            active_only=True,
        )

        # Parent assets: same company, active only
        self._filter_by_company(
            "parent",
            m.Asset.objects.all(),
            active_only=True,
        )
        self._exclude_self("parent")

        # ----------------------------------------------
        # Status policy: prevent choosing ASSIGNED here
        # (holder is workflow-only, and signals enforce consistency)
        # ----------------------------------------------
        if "status" in self.fields:
            allowed_statuses = [
                m.Asset.Status.AVAILABLE,
                m.Asset.Status.MAINTENANCE,
                m.Asset.Status.RETIRED,
            ]

            self.fields["status"].choices = [
                (value, label)
                for (value, label) in m.Asset.Status.choices
                if value in allowed_statuses
            ]

    # --------------------------------------------------
    # Field-level cleaning
    # --------------------------------------------------
    def clean_name(self):
        name = (self.cleaned_data.get("name") or "").strip()
        if not name:
            raise forms.ValidationError(_("Asset name cannot be empty."))
        return name

    def clean_code(self):
        code = (self.cleaned_data.get("code") or "").strip()
        if not code:
            raise forms.ValidationError(_("Asset code is required."))
        return code

    def clean_serial(self):
        serial = self.cleaned_data.get("serial")
        if serial is None:
            return None
        serial = serial.strip()
        return serial or None

    def clean_purchase_value(self):
        val = self.cleaned_data.get("purchase_value")
        if val is None:
            return None
        if val < 0:
            raise forms.ValidationError(_("Purchase value cannot be negative."))
        return val

    # --------------------------------------------------
    # Cross-field validation (defensive, UX-friendly)
    # --------------------------------------------------
    def clean(self):
        cleaned = super().clean()

        company = cleaned.get("company") or getattr(self.instance, "company", None)
        category = cleaned.get("category")
        department = cleaned.get("department")
        parent = cleaned.get("parent")
        status = cleaned.get("status")
        active = cleaned.get("active")

        # company must exist (create UX)
        if not company:
            self.add_error("company", _("Company is required."))
            return cleaned

        # Company consistency (UX layer; model/signals also enforce)
        if category and category.company_id != company.id:
            self.add_error("category", _("Category must belong to the same company."))

        if department and getattr(department, "company_id", None) != company.id:
            self.add_error("department", _("Department must belong to the same company."))

        if parent:
            if self.instance.pk and parent.pk == self.instance.pk:
                self.add_error("parent", _("Asset cannot be its own parent."))
            elif parent.company_id != company.id:
                self.add_error("parent", _("Parent asset must belong to the same company."))

        # Status restriction: no ASSIGNED here
        if status == m.Asset.Status.ASSIGNED:
            self.add_error(
                "status",
                _("Assigned status is not set here. Use Assign/Unassign workflow.")
            )

        # If retired → typically inactive (signals will enforce, but keep UX clear)
        if status == m.Asset.Status.RETIRED and active:
            # لا نجبرها هنا، فقط رسالة واضحة
            self.add_error(
                "active",
                _("Retired assets are typically archived automatically.")
            )

        return cleaned



# ============================================================
#  Workflow Forms (Assign / Unassign)
# ============================================================

class AssetAssignForm(forms.Form):
    """
    Workflow: Assign Asset to Employee (calls services.assign_asset)
    """
    employee = forms.ModelChoiceField(
        queryset=apps.get_model("hr", "Employee").objects.none()
    )
    date_from = forms.DateField(required=False, initial=date.today)
    note = forms.CharField(required=False, max_length=255)

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        self.asset: m.Asset = kwargs.pop("asset")

        # Optional: pre-selected employee
        self.assign_to_employee_id = kwargs.pop(
            "assign_to_employee_id",
            None,
        )

        super().__init__(*args, **kwargs)

        Employee = apps.get_model("hr", "Employee")

        qs = Employee.objects.all()
        if hasattr(Employee, "active"):
            qs = qs.filter(active=True)

        if hasattr(Employee, "company_id"):
            qs = qs.filter(company_id=self.asset.company_id)

        self.fields["employee"].queryset = qs

        # Auto-select employee when coming from Employee page
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
