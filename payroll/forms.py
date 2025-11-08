# payroll/forms.py
from __future__ import annotations
from django import forms
from django.db.models import Q
from base.models import Company
from base.company_context import get_company_id as get_current_company
from . import models as m


class _ScopedModelForm(forms.ModelForm):
    """
    - يقيّد الحقول المرتبطة بالشركة على الشركات المسموح بها.
    - يعيّن الشركة الحالية افتراضيًا عند الإنشاء.
    """
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

        allowed_companies = Company.objects.with_acl("view") if hasattr(Company.objects, "with_acl") else Company.objects.all()

        # ضبط حقل company (إن وجد)
        if "company" in self.fields:
            self.fields["company"].queryset = allowed_companies

        cur_id = get_current_company(self.request)  # returns an integer id
        if cur_id and "company" in self.fields and allowed_companies.filter(pk=cur_id).exists():
            if not getattr(self.instance, "pk", None):
                # initial can be a pk
                self.fields["company"].initial = cur_id

    def _filter_by_company(self, field_name: str, qs):
        if field_name not in self.fields:
            return
        # اختر شركة الفورم إن وُجدت وإلا شركات مسموح بها
        company_id = (
            self.data.get(self.add_prefix("company"))
            or self.initial.get("company")
            or getattr(self.instance, "company_id", None)
        )
        if company_id:
            self.fields[field_name].queryset = qs.filter(company_id=company_id)
        else:
            allowed_ids = Company.objects.with_acl("view").values("id") if hasattr(Company.objects, "with_acl") else Company.objects.values("id")
            # بعض الموديلات لا تحتوي company -> نعيد qs كما هو
            try:
                self.fields[field_name].queryset = qs.filter(company_id__in=allowed_ids)
            except Exception:
                self.fields[field_name].queryset = qs


# ============ Config / Master ============
class PayrollStructureForm(_ScopedModelForm):
    class Meta:
        model = m.PayrollStructure
        fields = ["name", "code", "use_worked_day_lines", "company"]


class SalaryRuleCategoryForm(forms.ModelForm):
    class Meta:
        model = m.SalaryRuleCategory
        fields = ["name", "code", "sequence"]


class RuleParameterForm(_ScopedModelForm):
    class Meta:
        model = m.RuleParameter
        fields = ["company", "code", "value"]


class SalaryRuleForm(forms.ModelForm):
    class Meta:
        model = m.SalaryRule
        fields = [
            "struct", "code", "name", "sequence",
            "category", "condition_select", "condition_python",
            "amount_python", "input_usage_employee", "unique_code_per_struct",
        ]


class InputTypeForm(_ScopedModelForm):
    class Meta:
        model = m.InputType
        fields = ["company", "name", "code", "active", "is_quantity"]


# ============ Period / Transactions ============
class PayrollPeriodForm(_ScopedModelForm):
    class Meta:
        model = m.PayrollPeriod
        fields = ["company", "date_from", "date_to", "month", "year", "state"]


class PayslipForm(_ScopedModelForm):
    class Meta:
        model = m.Payslip
        fields = [
            "company", "employee", "period",
            "department", "job",
            "struct", "note", "state",
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
