# payroll/access.py
# ------------------------------------------------------------
# Best-Practice Access Layer for Payroll Application
# ------------------------------------------------------------
# IMPORTANT:
# - This module contains NO business rules.
# - All access decisions come entirely from ACL (ObjectACL).
# - Views should rely on:
#       Model.acl_objects.with_acl("view")
#       Model.acl_objects.with_acl("change")
# - The only job of these functions is to provide a clean
#   standard interface used by templates or services.
# ------------------------------------------------------------

# NOTE:
# This module assumes that all ACL grants are handled centrally
# via base.acl_service.apply_default_acl and signals.


from __future__ import annotations

from django.contrib.auth import get_user_model

from payroll.models import (
    Payslip,
    PayslipLine,
    PayrollPeriod,
    EmployeeSalary,
    PayrollStructure,
    SalaryRuleCategory,
    SalaryRule,
    InputType,
    PayslipInput,
)
from base.acl_service import has_perm

User = get_user_model()


# ============================================================
# Generic helper
# ============================================================

def _can(user: User, obj, action: str) -> bool:
    """
    Thin wrapper over base ACL:
      - No business logic here.
      - Pure ObjectACL lookup via base.acl_service.has_perm().
    """
    return has_perm(obj, user, action)


# ============================================================
# 1) PayrollPeriod
# ============================================================

def can_view_period(user: User, period: PayrollPeriod) -> bool:
    return _can(user, period, "view")


def can_edit_period(user: User, period: PayrollPeriod) -> bool:
    return _can(user, period, "change")


def can_delete_period(user: User, period: PayrollPeriod) -> bool:
    return _can(user, period, "delete")


# ============================================================
# 2) Payslip
# ============================================================

def can_view_payslip(user: User, payslip: Payslip) -> bool:
    return _can(user, payslip, "view")


def can_edit_payslip(user: User, payslip: Payslip) -> bool:
    return _can(user, payslip, "change")


def can_delete_payslip(user: User, payslip: Payslip) -> bool:
    return _can(user, payslip, "delete")


def can_validate_payslip(user: User, payslip: Payslip) -> bool:
    # optional action supported by your ACL extras/core mapping
    return _can(user, payslip, "approve")


def can_pay_payslip(user: User, payslip: Payslip) -> bool:
    # optional extra action; keep as ACL-based (extras) if you use it
    return _can(user, payslip, "pay")


# ============================================================
# 3) PayslipLine
# ============================================================

def can_view_payslip_line(user: User, line: PayslipLine) -> bool:
    return _can(user, line, "view")


def can_edit_payslip_line(user: User, line: PayslipLine) -> bool:
    return _can(user, line, "change")


def can_delete_payslip_line(user: User, line: PayslipLine) -> bool:
    return _can(user, line, "delete")


# ============================================================
# 4) EmployeeSalary
# ============================================================

def can_view_employee_salary(user: User, salary: EmployeeSalary) -> bool:
    return _can(user, salary, "view")


def can_edit_employee_salary(user: User, salary: EmployeeSalary) -> bool:
    return _can(user, salary, "change")


def can_delete_employee_salary(user: User, salary: EmployeeSalary) -> bool:
    return _can(user, salary, "delete")


# ============================================================
# 5) PayrollStructure / SalaryRuleCategory / SalaryRule
# ============================================================

def can_view_structure(user: User, struct: PayrollStructure) -> bool:
    return _can(user, struct, "view")


def can_edit_structure(user: User, struct: PayrollStructure) -> bool:
    return _can(user, struct, "change")


def can_delete_structure(user: User, struct: PayrollStructure) -> bool:
    return _can(user, struct, "delete")


def can_view_salary_rule(user: User, rule: SalaryRule) -> bool:
    return _can(user, rule, "view")


def can_edit_salary_rule(user: User, rule: SalaryRule) -> bool:
    return _can(user, rule, "change")


def can_delete_salary_rule(user: User, rule: SalaryRule) -> bool:
    return _can(user, rule, "delete")


def can_view_rule_category(user: User, cat: SalaryRuleCategory) -> bool:
    return _can(user, cat, "view")


def can_edit_rule_category(user: User, cat: SalaryRuleCategory) -> bool:
    return _can(user, cat, "change")


def can_delete_rule_category(user: User, cat: SalaryRuleCategory) -> bool:
    return _can(user, cat, "delete")


# ============================================================
# 6) Input Types & PayslipInput
# ============================================================

def can_view_input_type(user: User, it: InputType) -> bool:
    return _can(user, it, "view")


def can_edit_input_type(user: User, it: InputType) -> bool:
    return _can(user, it, "change")


def can_delete_input_type(user: User, it: InputType) -> bool:
    return _can(user, it, "delete")


def can_view_payslip_input(user: User, pi: PayslipInput) -> bool:
    return _can(user, pi, "view")


def can_edit_payslip_input(user: User, pi: PayslipInput) -> bool:
    return _can(user, pi, "change")


def can_delete_payslip_input(user: User, pi: PayslipInput) -> bool:
    return _can(user, pi, "delete")
