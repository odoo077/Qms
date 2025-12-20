# payroll/views.py
from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DetailView

from base.views import BaseScopedListView, apply_search_filters
from base.acl_service import has_perm
from . import models as m
from . import forms as f


# ============================================================
# Helpers
# ============================================================

def _qs_with_acl(qs, action: str):
    """
    Return qs.with_acl(action) if supported, else return qs unchanged.
    """
    return qs.with_acl(action) if hasattr(qs, "with_acl") else qs


class _RequestFormKwargsMixin:
    """
    Ensures all forms receive request=... (needed for company scoping defaults).
    """
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs


class _ObjectACLQuerysetMixin:
    """
    Restrict object access (Detail/Update) by object-level ACL.
    - view: for Detail
    - change: for Update
    """
    acl_action = "view"  # override in subclasses

    def get_queryset(self):
        # Always start from model.objects; ACLManager is already attached as objects in your models.
        qs = self.model.objects.all()
        return _qs_with_acl(qs, self.acl_action)


class _ObjectACLPermissionMixin:
    """
    Final guard: even if queryset is permissive, enforce object ACL explicitly.
    """
    acl_action = "view"  # override

    def dispatch(self, request, *args, **kwargs):
        resp = super().dispatch(request, *args, **kwargs)
        # For CBVs, object is available after get_object in Detail/Update.
        # If it wasn't fetched yet, we don't block here.
        obj = getattr(self, "object", None)
        if obj is not None and not has_perm(obj, request.user, self.acl_action):
            raise PermissionDenied
        return resp


# ============================================================
# Config / Master
# ============================================================

class PayrollStructureListView(LoginRequiredMixin, BaseScopedListView, ListView):
    model = m.PayrollStructure
    template_name = "payroll/structure_list.html"
    paginate_by = 24

    def get_queryset(self):
        qs = _qs_with_acl(
            m.PayrollStructure.objects.select_related("company").order_by("name"),
            "view",
        )
        qs = apply_search_filters(self.request, qs, search_fields=["name", "code", "company__name"])
        return qs


class PayrollStructureCreateView(LoginRequiredMixin, _RequestFormKwargsMixin, CreateView):
    model = m.PayrollStructure
    form_class = f.PayrollStructureForm
    template_name = "payroll/structure_form.html"
    success_url = reverse_lazy("payroll:structure_list")


class PayrollStructureUpdateView(
    LoginRequiredMixin,
    _RequestFormKwargsMixin,
    _ObjectACLQuerysetMixin,
    _ObjectACLPermissionMixin,
    UpdateView,
):
    model = m.PayrollStructure
    form_class = f.PayrollStructureForm
    template_name = "payroll/structure_form.html"
    success_url = reverse_lazy("payroll:structure_list")
    acl_action = "change"


class SalaryRuleCategoryListView(LoginRequiredMixin, BaseScopedListView, ListView):
    model = m.SalaryRuleCategory
    template_name = "payroll/rule_category_list.html"
    paginate_by = 24

    def get_queryset(self):
        qs = _qs_with_acl(
            m.SalaryRuleCategory.objects.select_related("company").order_by("sequence", "name"),
            "view",
        )
        qs = apply_search_filters(self.request, qs, search_fields=["name", "code", "company__name"])
        return qs


class SalaryRuleCategoryCreateView(LoginRequiredMixin, _RequestFormKwargsMixin, CreateView):
    model = m.SalaryRuleCategory
    form_class = f.SalaryRuleCategoryForm
    template_name = "payroll/rule_category_form.html"
    success_url = reverse_lazy("payroll:rule_category_list")


class SalaryRuleCategoryUpdateView(
    LoginRequiredMixin,
    _RequestFormKwargsMixin,
    _ObjectACLQuerysetMixin,
    _ObjectACLPermissionMixin,
    UpdateView,
):
    model = m.SalaryRuleCategory
    form_class = f.SalaryRuleCategoryForm
    template_name = "payroll/rule_category_form.html"
    success_url = reverse_lazy("payroll:rule_category_list")
    acl_action = "change"


class RuleParameterListView(LoginRequiredMixin, BaseScopedListView, ListView):
    model = m.RuleParameter
    template_name = "payroll/rule_parameter_list.html"
    paginate_by = 24

    def get_queryset(self):
        qs = _qs_with_acl(
            m.RuleParameter.objects.select_related("company").order_by("code"),
            "view",
        )
        qs = apply_search_filters(self.request, qs, search_fields=["code", "company__name"])
        return qs


class RuleParameterCreateView(LoginRequiredMixin, _RequestFormKwargsMixin, CreateView):
    model = m.RuleParameter
    form_class = f.RuleParameterForm
    template_name = "payroll/rule_parameter_form.html"
    success_url = reverse_lazy("payroll:rule_parameter_list")


class RuleParameterUpdateView(
    LoginRequiredMixin,
    _RequestFormKwargsMixin,
    _ObjectACLQuerysetMixin,
    _ObjectACLPermissionMixin,
    UpdateView,
):
    model = m.RuleParameter
    form_class = f.RuleParameterForm
    template_name = "payroll/rule_parameter_form.html"
    success_url = reverse_lazy("payroll:rule_parameter_list")
    acl_action = "change"


class SalaryRuleListView(LoginRequiredMixin, BaseScopedListView, ListView):
    model = m.SalaryRule
    template_name = "payroll/salary_rule_list.html"
    paginate_by = 24

    def get_queryset(self):
        qs = _qs_with_acl(
            m.SalaryRule.objects.select_related("struct", "category", "struct__company", "category__company")
            .order_by("struct__name", "sequence", "id"),
            "view",
        )
        qs = apply_search_filters(
            self.request,
            qs,
            search_fields=["name", "code", "struct__name", "category__name", "struct__company__name"],
        )
        return qs


class SalaryRuleCreateView(LoginRequiredMixin, _RequestFormKwargsMixin, CreateView):
    model = m.SalaryRule
    form_class = f.SalaryRuleForm
    template_name = "payroll/salary_rule_form.html"
    success_url = reverse_lazy("payroll:salary_rule_list")


class SalaryRuleUpdateView(
    LoginRequiredMixin,
    _RequestFormKwargsMixin,
    _ObjectACLQuerysetMixin,
    _ObjectACLPermissionMixin,
    UpdateView,
):
    model = m.SalaryRule
    form_class = f.SalaryRuleForm
    template_name = "payroll/salary_rule_form.html"
    success_url = reverse_lazy("payroll:salary_rule_list")
    acl_action = "change"


class InputTypeListView(LoginRequiredMixin, BaseScopedListView, ListView):
    model = m.InputType
    template_name = "payroll/input_type_list.html"
    paginate_by = 24

    def get_queryset(self):
        qs = _qs_with_acl(
            m.InputType.objects.select_related("company").order_by("name"),
            "view",
        )
        qs = apply_search_filters(self.request, qs, search_fields=["name", "code", "company__name"])
        return qs


class InputTypeCreateView(LoginRequiredMixin, _RequestFormKwargsMixin, CreateView):
    model = m.InputType
    form_class = f.InputTypeForm
    template_name = "payroll/input_type_form.html"
    success_url = reverse_lazy("payroll:input_type_list")


class InputTypeUpdateView(
    LoginRequiredMixin,
    _RequestFormKwargsMixin,
    _ObjectACLQuerysetMixin,
    _ObjectACLPermissionMixin,
    UpdateView,
):
    model = m.InputType
    form_class = f.InputTypeForm
    template_name = "payroll/input_type_form.html"
    success_url = reverse_lazy("payroll:input_type_list")
    acl_action = "change"


# ============================================================
# Period / Transactions
# ============================================================

class PayrollPeriodListView(LoginRequiredMixin, BaseScopedListView, ListView):
    model = m.PayrollPeriod
    template_name = "payroll/period_list.html"
    paginate_by = 24

    def get_queryset(self):
        qs = _qs_with_acl(
            m.PayrollPeriod.objects.select_related("company").order_by("-year", "-month"),
            "view",
        )
        qs = apply_search_filters(
            self.request,
            qs,
            search_fields=["company__name", "year", "month", "state"],
        )
        return qs


class PayrollPeriodCreateView(LoginRequiredMixin, _RequestFormKwargsMixin, CreateView):
    model = m.PayrollPeriod
    form_class = f.PayrollPeriodForm
    template_name = "payroll/period_form.html"
    success_url = reverse_lazy("payroll:period_list")


class PayrollPeriodUpdateView(
    LoginRequiredMixin,
    _RequestFormKwargsMixin,
    _ObjectACLQuerysetMixin,
    _ObjectACLPermissionMixin,
    UpdateView,
):
    model = m.PayrollPeriod
    form_class = f.PayrollPeriodForm
    template_name = "payroll/period_form.html"
    success_url = reverse_lazy("payroll:period_list")
    acl_action = "change"


class PayrollPeriodDetailView(
    LoginRequiredMixin,
    _ObjectACLQuerysetMixin,
    _ObjectACLPermissionMixin,
    DetailView,
):
    model = m.PayrollPeriod
    template_name = "payroll/period_detail.html"
    acl_action = "view"

    def get_queryset(self):
        return super().get_queryset().select_related("company")


class PayslipListView(LoginRequiredMixin, BaseScopedListView, ListView):
    model = m.Payslip
    template_name = "payroll/payslip_list.html"
    paginate_by = 24

    def get_queryset(self):
        qs = _qs_with_acl(
            m.Payslip.objects.select_related(
                "company", "employee", "period", "department", "job", "struct"
            ).order_by("-period__year", "-period__month", "employee__name"),
            "view",
        )
        qs = apply_search_filters(
            self.request,
            qs,
            search_fields=[
                "employee__name",
                "company__name",
                "period__year",
                "period__month",
                "department__name",
                "job__name",
                "state",
            ],
        )
        return qs


class PayslipCreateView(LoginRequiredMixin, _RequestFormKwargsMixin, CreateView):
    model = m.Payslip
    form_class = f.PayslipForm
    template_name = "payroll/payslip_form.html"
    success_url = reverse_lazy("payroll:payslip_list")


class PayslipUpdateView(
    LoginRequiredMixin,
    _RequestFormKwargsMixin,
    _ObjectACLQuerysetMixin,
    _ObjectACLPermissionMixin,
    UpdateView,
):
    model = m.Payslip
    form_class = f.PayslipForm
    template_name = "payroll/payslip_form.html"
    success_url = reverse_lazy("payroll:payslip_list")
    acl_action = "change"

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()

        # Enforce object ACL first
        if not has_perm(self.object, request.user, "change"):
            raise PermissionDenied

        # Odoo-like: do not allow editing non-draft payslips from the UI form
        if getattr(self.object, "state", "draft") != "draft":
            raise PermissionDenied

        return super().dispatch(request, *args, **kwargs)


class PayslipDetailView(
    LoginRequiredMixin,
    _ObjectACLQuerysetMixin,
    _ObjectACLPermissionMixin,
    DetailView,
):
    model = m.Payslip
    template_name = "payroll/payslip_detail.html"
    acl_action = "view"

    def get_queryset(self):
        return super().get_queryset().select_related(
            "company", "employee", "period", "department", "job", "struct"
        )


class EmployeeSalaryListView(LoginRequiredMixin, BaseScopedListView, ListView):
    model = m.EmployeeSalary
    template_name = "payroll/employee_salary_list.html"
    paginate_by = 24

    def get_queryset(self):
        qs = _qs_with_acl(
            m.EmployeeSalary.objects.select_related("company", "employee").order_by("-date_start"),
            "view",
        )
        qs = apply_search_filters(
            self.request,
            qs,
            search_fields=["employee__name", "company__name", "date_start", "date_end"],
        )
        return qs


class EmployeeSalaryCreateView(LoginRequiredMixin, _RequestFormKwargsMixin, CreateView):
    model = m.EmployeeSalary
    form_class = f.EmployeeSalaryForm
    template_name = "payroll/employee_salary_form.html"
    success_url = reverse_lazy("payroll:employee_salary_list")


class EmployeeSalaryUpdateView(
    LoginRequiredMixin,
    _RequestFormKwargsMixin,
    _ObjectACLQuerysetMixin,
    _ObjectACLPermissionMixin,
    UpdateView,
):
    model = m.EmployeeSalary
    form_class = f.EmployeeSalaryForm
    template_name = "payroll/employee_salary_form.html"
    success_url = reverse_lazy("payroll:employee_salary_list")
    acl_action = "change"


class EmployeeSalaryDetailView(
    LoginRequiredMixin,
    _ObjectACLQuerysetMixin,
    _ObjectACLPermissionMixin,
    DetailView,
):
    model = m.EmployeeSalary
    template_name = "payroll/employee_salary_detail.html"
    acl_action = "view"

    def get_queryset(self):
        return super().get_queryset().select_related("company", "employee")
