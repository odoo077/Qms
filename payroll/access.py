# payroll/access.py
# ------------------------------------------------------------
# High-level business rules for the Payroll app.
#
# DOES NOT:
#   - assign ObjectACL permissions
#   - depend on any fixed roles / groups
#   - rely on any fields not present in payroll/models.py
#
# ONLY:
#   - business logic decisions using employee hierarchy
#   - company scope (via base.access)
# ------------------------------------------------------------

from __future__ import annotations

from typing import Optional
from django.contrib.auth import get_user_model

from hr.models import Employee, Department
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
from base.access import (
    get_employee,
    is_in_same_company,
    is_manager_of,
    user_is_in_manager_chain,
    is_in_same_department,
)

User = get_user_model()


# ============================================================
# 1) PayrollPeriod business rules
# ============================================================

def can_view_period(user: User, period: PayrollPeriod) -> bool:
    """
    You can view a PayrollPeriod if:
      - same company
      - you manage employees in that company
      - OR any employee under you has payslips in this period
    """
    if not user or not user.is_authenticated:
        return False

    if not is_in_same_company(user, period.company_id):
        return False

    me = get_employee(user)
    if not me:
        return False

    # Manager of employees → sees payroll periods
    if Employee.objects.filter(manager_id=me.id, company_id=period.company_id).exists():
        return True

    # Manager in chain for employees that have payslips in this period
    payslips = Payslip.objects.filter(period=period).select_related("employee")
    for ps in payslips:
        if is_manager_of(user, ps.employee) or user_is_in_manager_chain(user, ps.employee):
            return True

    # Regular employees in same company can see the period header (no details)
    return True


def can_edit_period(user: User, period: PayrollPeriod) -> bool:
    """
    Editable if user manages employees within this company.
    (High-level business rule only; ACL enforces final access)
    """
    if not user or not user.is_authenticated:
        return False

    if not is_in_same_company(user, period.company_id):
        return False

    me = get_employee(user)
    if not me:
        return False

    return Employee.objects.filter(manager_id=me.id, company_id=period.company_id).exists()


# ============================================================
# 2) Payslip business rules
# ============================================================

def can_view_payslip(user: User, payslip: Payslip) -> bool:
    """
    Payslip visible if:
      - same company
      - self (employee)
      - direct manager
      - parent manager in chain
      - same department
    """
    if not user or not user.is_authenticated:
        return False

    if not is_in_same_company(user, payslip.company_id):
        return False

    me = get_employee(user)
    if not me:
        return False

    # Self
    if payslip.employee_id == me.id:
        return True

    # Manager
    if is_manager_of(user, payslip.employee):
        return True

    # Manager chain
    if user_is_in_manager_chain(user, payslip.employee):
        return True

    # Same department
    if is_in_same_department(user, payslip.employee):
        return True

    return False


def can_edit_payslip(user: User, payslip: Payslip) -> bool:
    """
    Editing allowed if:
      - manager of employee
      - OR parent manager chain
    (Self cannot edit — payroll is admin/manager task)
    """
    if not user or not user.is_authenticated:
        return False

    if not is_in_same_company(user, payslip.company_id):
        return False

    me = get_employee(user)
    if not me:
        return False

    # Managers can edit
    if is_manager_of(user, payslip.employee):
        return True

    if user_is_in_manager_chain(user, payslip.employee):
        return True

    return False


# ============================================================
# 3) PayslipLine business rules
# ============================================================

def can_view_payslip_line(user: User, line: PayslipLine) -> bool:
    """Visible if user can view the parent payslip."""
    return can_view_payslip(user, line.payslip)


def can_edit_payslip_line(user: User, line: PayslipLine) -> bool:
    """Editable if user can edit the parent payslip."""
    return can_edit_payslip(user, line.payslip)


# ============================================================
# 4) EmployeeSalary business rules
# ============================================================

def can_view_employee_salary(user: User, salary: EmployeeSalary) -> bool:
    """
    Salary visible if:
      - same company
      - self (employee)
      - direct manager
      - manager in chain
    """
    if not user or not user.is_authenticated:
        return False

    if not is_in_same_company(user, salary.company_id):
        return False

    me = get_employee(user)
    if not me:
        return False

    # Self
    if salary.employee_id == me.id:
        return True

    # Manager
    if is_manager_of(user, salary.employee):
        return True

    # Parent manager
    if user_is_in_manager_chain(user, salary.employee):
        return True

    return False


def can_edit_employee_salary(user: User, salary: EmployeeSalary) -> bool:
    """
    Editing allowed if:
      - manager of the employee
      - OR manager in parent chain
    """
    if not user or not user.is_authenticated:
        return False

    if not is_in_same_company(user, salary.company_id):
        return False

    me = get_employee(user)
    if not me:
        return False

    if is_manager_of(user, salary.employee):
        return True

    if user_is_in_manager_chain(user, salary.employee):
        return True

    return False


# ============================================================
# 5) PayrollStructure / SalaryRuleCategory / SalaryRule
# ============================================================

def can_view_structure(user: User, struct: PayrollStructure) -> bool:
    """
    Structure is company-level definition.
    Visible to all employees in the company.
    """
    if not user or not user.is_authenticated:
        return False

    return is_in_same_company(user, struct.company_id)


def can_edit_structure(user: User, struct: PayrollStructure) -> bool:
    """
    Editable if user manages employees within this company.
    """
    if not user or not user.is_authenticated:
        return False

    if not is_in_same_company(user, struct.company_id):
        return False

    me = get_employee(user)
    if not me:
        return False

    return Employee.objects.filter(manager_id=me.id, company_id=struct.company_id).exists()


def can_view_salary_rule(user: User, rule: SalaryRule) -> bool:
    """Visible if user can view the parent structure."""
    return can_view_structure(user, rule.struct)


def can_edit_salary_rule(user: User, rule: SalaryRule) -> bool:
    """Editable if user can edit the parent structure."""
    return can_edit_structure(user, rule.struct)


def can_view_rule_category(user: User, cat: SalaryRuleCategory) -> bool:
    """Categories are global — visible to all authenticated users."""
    return bool(user and user.is_authenticated)


def can_edit_rule_category(user: User, cat: SalaryRuleCategory) -> bool:
    """
    Editing allowed if user manages employees in any company.
    """
    if not user or not user.is_authenticated:
        return False

    me = get_employee(user)
    if not me:
        return False

    return Employee.objects.filter(manager_id=me.id).exists()


# ============================================================
# 6) Input Types & PayslipInput
# ============================================================

def can_view_input_type(user: User, it: InputType) -> bool:
    return is_in_same_company(user, it.company_id)


def can_edit_input_type(user: User, it: InputType) -> bool:
    # Manager-level editing
    if not user or not user.is_authenticated:
        return False

    if not is_in_same_company(user, it.company_id):
        return False

    me = get_employee(user)
    if not me:
        return False

    return Employee.objects.filter(manager_id=me.id, company_id=it.company_id).exists()


def can_view_payslip_input(user: User, pi: PayslipInput) -> bool:
    """Viewable if user can view the parent payslip."""
    return can_view_payslip(user, pi.payslip)


def can_edit_payslip_input(user: User, pi: PayslipInput) -> bool:
    """Editable if user can edit the parent payslip."""
    return can_edit_payslip(user, pi.payslip)
