# payroll/views.py

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.urls import reverse_lazy
from django.views.generic import (
    ListView,
    CreateView,
    UpdateView,
    DetailView,
    DeleteView,
)

from . import models as m
from . import forms as f


# ============================================================
# Configuration / Master Data
# ============================================================

# ------------------------------------------------------------
# Payroll Structure
# ------------------------------------------------------------

class PayrollStructureListView(LoginRequiredMixin, ListView):
    model = m.PayrollStructure
    template_name = "payroll/structure_list.html"
    paginate_by = 24
    ordering = ["name"]


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


class PayrollStructureDeleteView(LoginRequiredMixin, DeleteView):
    model = m.PayrollStructure
    template_name = "partials/confirm_delete.html"
    success_url = reverse_lazy("payroll:structure_list")


# ------------------------------------------------------------
# Salary Rule Category
# ------------------------------------------------------------

class SalaryRuleCategoryListView(LoginRequiredMixin, ListView):
    model = m.SalaryRuleCategory
    template_name = "payroll/rule_category_list.html"
    paginate_by = 24
    ordering = ["sequence", "name"]


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


class SalaryRuleCategoryDeleteView(LoginRequiredMixin, DeleteView):
    model = m.SalaryRuleCategory
    template_name = "partials/confirm_delete.html"
    success_url = reverse_lazy("payroll:rule_category_list")


# ------------------------------------------------------------
# Rule Parameter
# ------------------------------------------------------------

class RuleParameterListView(LoginRequiredMixin, ListView):
    model = m.RuleParameter
    template_name = "payroll/rule_parameter_list.html"
    paginate_by = 24
    ordering = ["code"]


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


class RuleParameterDeleteView(LoginRequiredMixin, DeleteView):
    model = m.RuleParameter
    template_name = "partials/confirm_delete.html"
    success_url = reverse_lazy("payroll:rule_parameter_list")


# ------------------------------------------------------------
# Salary Rule
# ------------------------------------------------------------

class SalaryRuleListView(LoginRequiredMixin, ListView):
    model = m.SalaryRule
    template_name = "payroll/salary_rule_list.html"
    paginate_by = 24

    def get_queryset(self):
        return (
            m.SalaryRule.objects
            .select_related("struct", "category", "struct__company", "category__company")
            .order_by("struct__name", "sequence")
        )


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


class SalaryRuleDeleteView(LoginRequiredMixin, DeleteView):
    model = m.SalaryRule
    template_name = "partials/confirm_delete.html"
    success_url = reverse_lazy("payroll:salary_rule_list")


# ------------------------------------------------------------
# Input Type
# ------------------------------------------------------------

class InputTypeListView(LoginRequiredMixin, ListView):
    model = m.InputType
    template_name = "payroll/input_type_list.html"
    paginate_by = 24
    ordering = ["name"]


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


class InputTypeDeleteView(LoginRequiredMixin, DeleteView):
    model = m.InputType
    template_name = "partials/confirm_delete.html"
    success_url = reverse_lazy("payroll:input_type_list")


# ============================================================
# Periods / Transactions
# ============================================================

# ------------------------------------------------------------
# Payroll Period
# ------------------------------------------------------------

class PayrollPeriodListView(LoginRequiredMixin, ListView):
    model = m.PayrollPeriod
    template_name = "payroll/period_list.html"
    paginate_by = 24
    ordering = ["-year", "-month"]


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


class PayrollPeriodDeleteView(LoginRequiredMixin, DeleteView):
    model = m.PayrollPeriod
    template_name = "partials/confirm_delete.html"
    success_url = reverse_lazy("payroll:period_list")


# ------------------------------------------------------------
# Payslip
# ------------------------------------------------------------

class PayslipListView(LoginRequiredMixin, ListView):
    model = m.Payslip
    template_name = "payroll/payslip_list.html"
    paginate_by = 24

    def get_queryset(self):
        return (
            m.Payslip.objects
            .select_related(
                "company",
                "employee",
                "period",
                "department",
                "job",
                "struct",
            )
            .order_by("-period__year", "-period__month", "employee__name")
        )


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

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.state != "draft":
            raise PermissionDenied("Only draft payslips can be edited.")
        return super().dispatch(request, *args, **kwargs)


class PayslipDetailView(LoginRequiredMixin, DetailView):
    model = m.Payslip
    template_name = "payroll/payslip_detail.html"


class PayslipDeleteView(LoginRequiredMixin, DeleteView):
    model = m.Payslip
    template_name = "partials/confirm_delete.html"
    success_url = reverse_lazy("payroll:payslip_list")


# ------------------------------------------------------------
# Payslip Input
# ------------------------------------------------------------

class PayslipInputListView(LoginRequiredMixin, ListView):
    model = m.PayslipInput
    template_name = "payroll/payslip_input_list.html"
    paginate_by = 24
    ordering = ["payslip", "sequence"]


class PayslipInputCreateView(LoginRequiredMixin, CreateView):
    model = m.PayslipInput
    form_class = f.PayslipInputForm
    template_name = "payroll/payslip_input_form.html"
    success_url = reverse_lazy("payroll:payslip_input_list")


class PayslipInputUpdateView(LoginRequiredMixin, UpdateView):
    model = m.PayslipInput
    form_class = f.PayslipInputForm
    template_name = "payroll/payslip_input_form.html"
    success_url = reverse_lazy("payroll:payslip_input_list")


class PayslipInputDeleteView(LoginRequiredMixin, DeleteView):
    model = m.PayslipInput
    template_name = "partials/confirm_delete.html"
    success_url = reverse_lazy("payroll:payslip_input_list")


# ------------------------------------------------------------
# Employee Salary
# ------------------------------------------------------------

class EmployeeSalaryListView(LoginRequiredMixin, ListView):
    model = m.EmployeeSalary
    template_name = "payroll/employee_salary_list.html"
    paginate_by = 24
    ordering = ["-date_start"]


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


class EmployeeSalaryDeleteView(LoginRequiredMixin, DeleteView):
    model = m.EmployeeSalary
    template_name = "partials/confirm_delete.html"
    success_url = reverse_lazy("payroll:employee_salary_list")
