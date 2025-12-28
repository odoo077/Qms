# payroll/urls.py

from django.urls import path
from . import views as v

app_name = "payroll"

urlpatterns = [

    # =========================================================
    # Default
    # =========================================================
    path("", v.PayslipListView.as_view(), name="index"),

    # =========================================================
    # Payroll Structures
    # =========================================================
    path("structures/", v.PayrollStructureListView.as_view(), name="structure_list"),
    path("structures/new/", v.PayrollStructureCreateView.as_view(), name="structure_create"),
    path("structures/<int:pk>/edit/", v.PayrollStructureUpdateView.as_view(), name="structure_edit"),
    path("structures/<int:pk>/delete/", v.PayrollStructureDeleteView.as_view(), name="structure_delete"),

    # =========================================================
    # Salary Rule Categories
    # =========================================================
    path("rule-categories/", v.SalaryRuleCategoryListView.as_view(), name="rule_category_list"),
    path("rule-categories/new/", v.SalaryRuleCategoryCreateView.as_view(), name="rule_category_create"),
    path("rule-categories/<int:pk>/edit/", v.SalaryRuleCategoryUpdateView.as_view(), name="rule_category_edit"),
    path("rule-categories/<int:pk>/delete/", v.SalaryRuleCategoryDeleteView.as_view(), name="rule_category_delete"),

    # =========================================================
    # Rule Parameters
    # =========================================================
    path("parameters/", v.RuleParameterListView.as_view(), name="rule_parameter_list"),
    path("parameters/new/", v.RuleParameterCreateView.as_view(), name="rule_parameter_create"),
    path("parameters/<int:pk>/edit/", v.RuleParameterUpdateView.as_view(), name="rule_parameter_edit"),
    path("parameters/<int:pk>/delete/", v.RuleParameterDeleteView.as_view(), name="rule_parameter_delete"),

    # =========================================================
    # Salary Rules
    # =========================================================
    path("rules/", v.SalaryRuleListView.as_view(), name="salary_rule_list"),
    path("rules/new/", v.SalaryRuleCreateView.as_view(), name="salary_rule_create"),
    path("rules/<int:pk>/edit/", v.SalaryRuleUpdateView.as_view(), name="salary_rule_edit"),
    path("rules/<int:pk>/delete/", v.SalaryRuleDeleteView.as_view(), name="salary_rule_delete"),

    # =========================================================
    # Input Types
    # =========================================================
    path("input-types/", v.InputTypeListView.as_view(), name="input_type_list"),
    path("input-types/new/", v.InputTypeCreateView.as_view(), name="input_type_create"),
    path("input-types/<int:pk>/edit/", v.InputTypeUpdateView.as_view(), name="input_type_edit"),
    path("input-types/<int:pk>/delete/", v.InputTypeDeleteView.as_view(), name="input_type_delete"),

    # =========================================================
    # Payroll Periods
    # =========================================================
    path("periods/", v.PayrollPeriodListView.as_view(), name="period_list"),
    path("periods/new/", v.PayrollPeriodCreateView.as_view(), name="period_create"),
    path("periods/<int:pk>/edit/", v.PayrollPeriodUpdateView.as_view(), name="period_edit"),
    path("periods/<int:pk>/", v.PayrollPeriodDetailView.as_view(), name="period_detail"),
    path("periods/<int:pk>/delete/", v.PayrollPeriodDeleteView.as_view(), name="period_delete"),

    # =========================================================
    # Payslips
    # =========================================================
    path("payslips/", v.PayslipListView.as_view(), name="payslip_list"),
    path("payslips/new/", v.PayslipCreateView.as_view(), name="payslip_create"),
    path("payslips/<int:pk>/edit/", v.PayslipUpdateView.as_view(), name="payslip_edit"),
    path("payslips/<int:pk>/", v.PayslipDetailView.as_view(), name="payslip_detail"),
    path("payslips/<int:pk>/delete/", v.PayslipDeleteView.as_view(), name="payslip_delete"),

    # =========================================================
    # Payslip Inputs
    # =========================================================
    path("payslip-inputs/", v.PayslipInputListView.as_view(), name="payslip_input_list"),
    path("payslip-inputs/new/", v.PayslipInputCreateView.as_view(), name="payslip_input_create"),
    path("payslip-inputs/<int:pk>/edit/", v.PayslipInputUpdateView.as_view(), name="payslip_input_edit"),
    path("payslip-inputs/<int:pk>/delete/", v.PayslipInputDeleteView.as_view(), name="payslip_input_delete"),

    # =========================================================
    # Employee Salary History
    # =========================================================
    path("salaries/", v.EmployeeSalaryListView.as_view(), name="employee_salary_list"),
    path("salaries/new/", v.EmployeeSalaryCreateView.as_view(), name="employee_salary_create"),
    path("salaries/<int:pk>/edit/", v.EmployeeSalaryUpdateView.as_view(), name="employee_salary_edit"),
    path("salaries/<int:pk>/", v.EmployeeSalaryDetailView.as_view(), name="employee_salary_detail"),
    path("salaries/<int:pk>/delete/", v.EmployeeSalaryDeleteView.as_view(), name="employee_salary_delete"),
]
