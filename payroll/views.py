# payroll/views.py
from __future__ import annotations
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DetailView
from django.db.models import Q

from base.views import BaseScopedListView, apply_search_filters
from . import models as m
from . import forms as f


# ========= Helpers =========
def _with_acl_or_all(qs):
    """يعيد qs.with_acl('view') إن كان مدعومًا، وإلا يعيد qs كما هو."""
    return qs.with_acl("view") if hasattr(qs, "with_acl") else qs


# ========= Config / Master =========
class PayrollStructureListView(LoginRequiredMixin, BaseScopedListView, ListView):
    model = m.PayrollStructure
    template_name = "payroll/structure_list.html"
    paginate_by = 24

    def get_queryset(self):
        qs = m.PayrollStructure.objects.select_related("company").order_by("name")
        qs = apply_search_filters(self.request, qs, search_fields=["name", "code", "company__name"])
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_add"] = self.request.user.has_perm("payroll.add_payrollstructure")
        return ctx


class PayrollStructureCreateView(LoginRequiredMixin, CreateView):
    model = m.PayrollStructure
    form_class = f.PayrollStructureForm
    template_name = "payroll/structure_form.html"
    success_url = reverse_lazy("payroll:structure_list")


class PayrollStructureUpdateView(LoginRequiredMixin, UpdateView):
    model = m.PayrollStructure
    form_class = f.PayrollStructureForm
    template_name = "payroll/structure_form.html"
    success_url = reverse_lazy("payroll:structure_list")


class SalaryRuleCategoryListView(LoginRequiredMixin, ListView):
    model = m.SalaryRuleCategory
    template_name = "payroll/rule_category_list.html"
    paginate_by = 24

    def get_queryset(self):
        qs = m.SalaryRuleCategory.objects.order_by("sequence", "name")
        qs = apply_search_filters(self.request, qs, search_fields=["name", "code"])
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_add"] = self.request.user.has_perm("payroll.add_salaryrulecategory")
        return ctx


class SalaryRuleCategoryCreateView(LoginRequiredMixin, CreateView):
    model = m.SalaryRuleCategory
    form_class = f.SalaryRuleCategoryForm
    template_name = "payroll/rule_category_form.html"
    success_url = reverse_lazy("payroll:rule_category_list")


class SalaryRuleCategoryUpdateView(LoginRequiredMixin, UpdateView):
    model = m.SalaryRuleCategory
    form_class = f.SalaryRuleCategoryForm
    template_name = "payroll/rule_category_form.html"
    success_url = reverse_lazy("payroll:rule_category_list")


class RuleParameterListView(LoginRequiredMixin, BaseScopedListView, ListView):
    model = m.RuleParameter
    template_name = "payroll/rule_parameter_list.html"
    paginate_by = 24

    def get_queryset(self):
        qs = m.RuleParameter.objects.select_related("company").order_by("code")
        qs = apply_search_filters(self.request, qs, search_fields=["code", "company__name"])
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_add"] = self.request.user.has_perm("payroll.add_ruleparameter")
        return ctx


class RuleParameterCreateView(LoginRequiredMixin, CreateView):
    model = m.RuleParameter
    form_class = f.RuleParameterForm
    template_name = "payroll/rule_parameter_form.html"
    success_url = reverse_lazy("payroll:rule_parameter_list")


class RuleParameterUpdateView(LoginRequiredMixin, UpdateView):
    model = m.RuleParameter
    form_class = f.RuleParameterForm
    template_name = "payroll/rule_parameter_form.html"
    success_url = reverse_lazy("payroll:rule_parameter_list")


class SalaryRuleListView(LoginRequiredMixin, ListView):
    model = m.SalaryRule
    template_name = "payroll/salary_rule_list.html"
    paginate_by = 24

    def get_queryset(self):
        qs = (
            m.SalaryRule.objects
            .select_related("struct", "category", "struct__company")
            .order_by("struct__name", "sequence")
        )
        qs = apply_search_filters(
            self.request, qs,
            search_fields=["name", "code", "struct__name", "category__name"]
        )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_add"] = self.request.user.has_perm("payroll.add_salaryrule")
        return ctx


class SalaryRuleCreateView(LoginRequiredMixin, CreateView):
    model = m.SalaryRule
    form_class = f.SalaryRuleForm
    template_name = "payroll/salary_rule_form.html"
    success_url = reverse_lazy("payroll:salary_rule_list")


class SalaryRuleUpdateView(LoginRequiredMixin, UpdateView):
    model = m.SalaryRule
    form_class = f.SalaryRuleForm
    template_name = "payroll/salary_rule_form.html"
    success_url = reverse_lazy("payroll:salary_rule_list")


class InputTypeListView(LoginRequiredMixin, BaseScopedListView, ListView):
    model = m.InputType
    template_name = "payroll/input_type_list.html"
    paginate_by = 24

    def get_queryset(self):
        qs = m.InputType.objects.select_related("company").order_by("name")
        qs = apply_search_filters(self.request, qs, search_fields=["name", "code", "company__name"])
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_add"] = self.request.user.has_perm("payroll.add_inputtype")
        return ctx


class InputTypeCreateView(LoginRequiredMixin, CreateView):
    model = m.InputType
    form_class = f.InputTypeForm
    template_name = "payroll/input_type_form.html"
    success_url = reverse_lazy("payroll:input_type_list")


class InputTypeUpdateView(LoginRequiredMixin, UpdateView):
    model = m.InputType
    form_class = f.InputTypeForm
    template_name = "payroll/input_type_form.html"
    success_url = reverse_lazy("payroll:input_type_list")


# ========= Period / Transactions =========
class PayrollPeriodListView(LoginRequiredMixin, BaseScopedListView, ListView):
    model = m.PayrollPeriod
    template_name = "payroll/period_list.html"
    paginate_by = 24

    def get_queryset(self):
        qs = _with_acl_or_all(m.PayrollPeriod.objects).select_related("company").order_by("-year", "-month")
        qs = apply_search_filters(
            self.request, qs,
            search_fields=["company__name", "year", "month", "state"]
        )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_add"] = self.request.user.has_perm("payroll.add_payrollperiod")
        return ctx


class PayrollPeriodCreateView(LoginRequiredMixin, CreateView):
    model = m.PayrollPeriod
    form_class = f.PayrollPeriodForm
    template_name = "payroll/period_form.html"
    success_url = reverse_lazy("payroll:period_list")


class PayrollPeriodUpdateView(LoginRequiredMixin, UpdateView):
    model = m.PayrollPeriod
    form_class = f.PayrollPeriodForm
    template_name = "payroll/period_form.html"
    success_url = reverse_lazy("payroll:period_list")


class PayrollPeriodDetailView(LoginRequiredMixin, DetailView):
    model = m.PayrollPeriod
    template_name = "payroll/period_detail.html"

    def get_queryset(self):
        return _with_acl_or_all(m.PayrollPeriod.objects).select_related("company")


class PayslipListView(LoginRequiredMixin, BaseScopedListView, ListView):
    model = m.Payslip
    template_name = "payroll/payslip_list.html"
    paginate_by = 24

    def get_queryset(self):
        qs = (
            _with_acl_or_all(m.Payslip.objects)
            .select_related("company", "employee", "period", "department", "job", "struct")
            .order_by("-period__year", "-period__month", "employee__name")
        )
        qs = apply_search_filters(
            self.request, qs,
            search_fields=[
                "employee__name", "company__name", "period__year", "period__month",
                "department__name", "job__name", "state"
            ],
        )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_add"] = self.request.user.has_perm("payroll.add_payslip")
        return ctx


class PayslipCreateView(LoginRequiredMixin, CreateView):
    model = m.Payslip
    form_class = f.PayslipForm
    template_name = "payroll/payslip_form.html"
    success_url = reverse_lazy("payroll:payslip_list")


class PayslipUpdateView(LoginRequiredMixin, UpdateView):
    model = m.Payslip
    form_class = f.PayslipForm
    template_name = "payroll/payslip_form.html"
    success_url = reverse_lazy("payroll:payslip_list")


class PayslipDetailView(LoginRequiredMixin, DetailView):
    model = m.Payslip
    template_name = "payroll/payslip_detail.html"

    def get_queryset(self):
        return (
            _with_acl_or_all(m.Payslip.objects)
            .select_related("company", "employee", "period", "department", "job", "struct")
        )


class EmployeeSalaryListView(LoginRequiredMixin, BaseScopedListView, ListView):
    model = m.EmployeeSalary
    template_name = "payroll/employee_salary_list.html"
    paginate_by = 24

    def get_queryset(self):
        qs = _with_acl_or_all(m.EmployeeSalary.objects).select_related("company", "employee").order_by("-date_start")
        qs = apply_search_filters(
            self.request, qs,
            search_fields=["employee__name", "company__name", "date_start", "date_end"]
        )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_add"] = self.request.user.has_perm("payroll.add_employeesalary")
        return ctx


class EmployeeSalaryCreateView(LoginRequiredMixin, CreateView):
    model = m.EmployeeSalary
    form_class = f.EmployeeSalaryForm
    template_name = "payroll/employee_salary_form.html"
    success_url = reverse_lazy("payroll:employee_salary_list")


class EmployeeSalaryUpdateView(LoginRequiredMixin, UpdateView):
    model = m.EmployeeSalary
    form_class = f.EmployeeSalaryForm
    template_name = "payroll/employee_salary_form.html"
    success_url = reverse_lazy("payroll:employee_salary_list")


class EmployeeSalaryDetailView(LoginRequiredMixin, DetailView):
    model = m.EmployeeSalary
    template_name = "payroll/employee_salary_detail.html"

    def get_queryset(self):
        return _with_acl_or_all(m.EmployeeSalary.objects).select_related("company", "employee")
