# payroll/forms.py
from __future__ import annotations

from django import forms

from base.models import Company
from base.company_context import get_company_id as get_current_company

from . import models as m


# ============================================================
# Base Scoped ModelForm (ACL + Company aware)
# ============================================================

class _ScopedModelForm(forms.ModelForm):
    """
    Base reusable scoped form:
    - Limits company-related fields to companies the user can view (ACL).
    - Sets current company automatically on create.
    """

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

        # Companies visible by ACL (fallback to all if ACL manager not available)
        allowed_companies = (
            Company.objects.with_acl("view")
            if hasattr(Company.objects, "with_acl")
            else Company.objects.all()
        )

        # ----------------------------------------------------
        # Company field scoping + default
        # ----------------------------------------------------
        if "company" in self.fields:
            self.fields["company"].queryset = allowed_companies

            cur_id = get_current_company(self.request)
            if cur_id and allowed_companies.filter(pk=cur_id).exists():
                if not getattr(self.instance, "pk", None):
                    self.fields["company"].initial = cur_id

    # --------------------------------------------------------
    # Helper: filter FK fields by selected / instance company
    # --------------------------------------------------------
    def _filter_by_company(self, field_name: str, qs):
        if field_name not in self.fields:
            return

        company_id = (
            self.data.get(self.add_prefix("company"))
            or self.initial.get("company")
            or getattr(self.instance, "company_id", None)
        )

        if company_id:
            try:
                self.fields[field_name].queryset = qs.filter(company_id=company_id)
            except Exception:
                # Model has no company field
                self.fields[field_name].queryset = qs
        else:
            try:
                allowed_ids = (
                    Company.objects.with_acl("view").values("id")
                    if hasattr(Company.objects, "with_acl")
                    else Company.objects.values("id")
                )
                self.fields[field_name].queryset = qs.filter(company_id__in=allowed_ids)
            except Exception:
                self.fields[field_name].queryset = qs


# ============================================================
# Configuration / Master Data
# ============================================================

class PayrollStructureForm(_ScopedModelForm):
    class Meta:
        model = m.PayrollStructure
        fields = ["company", "name", "code", "use_worked_day_lines"]


class SalaryRuleCategoryForm(_ScopedModelForm):
    """
    Salary Rule Category MUST be company-scoped
    (fix for multi-company + ACL consistency).
    """
    class Meta:
        model = m.SalaryRuleCategory
        fields = ["company", "name", "code", "sequence"]


class RuleParameterForm(_ScopedModelForm):
    class Meta:
        model = m.RuleParameter
        fields = ["company", "code", "value"]


class SalaryRuleForm(forms.ModelForm):
    """
    Salary rules are indirectly company-scoped via PayrollStructure,
    therefore no direct company field here.
    """
    class Meta:
        model = m.SalaryRule
        fields = [
            "struct",
            "code",
            "name",
            "sequence",
            "category",
            "condition_select",
            "condition_python",
            "amount_python",
            "input_usage_employee",
            "unique_code_per_struct",
        ]


class InputTypeForm(_ScopedModelForm):
    class Meta:
        model = m.InputType
        fields = ["company", "name", "code", "active", "is_quantity"]


# ============================================================
# Periods / Transactions
# ============================================================

class PayrollPeriodForm(_ScopedModelForm):
    class Meta:
        model = m.PayrollPeriod
        fields = ["company", "date_from", "date_to", "month", "year", "state"]


class PayslipForm(_ScopedModelForm):
    class Meta:
        model = m.Payslip
        fields = [
            "company",
            "employee",
            "period",
            "department",
            "job",
            "struct",
            "note",
            "state",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        from hr.models import Employee, Department, Job

        self._filter_by_company("employee", Employee.objects.all())
        self._filter_by_company("department", Department.objects.all())
        self._filter_by_company("job", Job.objects.all())
        self._filter_by_company("period", m.PayrollPeriod.objects.all())
        self._filter_by_company("struct", m.PayrollStructure.objects.all())


class EmployeeSalaryForm(_ScopedModelForm):
    class Meta:
        model = m.EmployeeSalary
        fields = ["company", "employee", "amount", "date_start", "date_end", "note"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        from hr.models import Employee
        self._filter_by_company("employee", Employee.objects.all())
