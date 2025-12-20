# file: hr/access.py

from base.access import (
    user_is_hr_manager,
    is_in_same_company,
    get_employee,
    is_manager_of,
    user_is_in_manager_chain,
)
from hr.models import Department, Employee


"""
hr.access

⚠️ IMPORTANT ARCHITECTURAL NOTE

This module contains UI-level permission helpers that are
INTENTIONALLY scoped to the `hr` application only.

These functions:
- can_view_department
- can_edit_department
- can_view_employee
- can_edit_employee

are meant for:
- View-level access decisions
- Human-readable business rules
- HR-specific permission logic

They are NOT the system-wide source of truth for security.

System-wide authorization is enforced by:
- base.acl_service (Object-level ACL)
- BaseScoped*View mixins

Do NOT reuse these helpers outside the `hr` app.
"""


# ============================================================
#  Department Visibility (View)
# ============================================================

def can_view_department(user, department: Department) -> bool:
    """
    جميع المستخدمين داخل نفس الشركة يمكنهم رؤية أي قسم.
    """
    if not user or not user.is_authenticated:
        return False

    return is_in_same_company(user, department.company_id)


# ============================================================
#  Department Edit Permissions
# ============================================================

def can_edit_department(user, department: Department) -> bool:
    if not user or not user.is_authenticated:
        return False

    if user_is_hr_manager(user):
        return True

    me = get_employee(user)
    if not me:
        return False

    if department.manager_id == me.id:
        return True

    if department.get_ancestors().filter(manager_id=me.id).exists():
        return True

    return False


# ============================================================
#  Employee Visibility (View)
# ============================================================

def can_view_employee(user, employee: Employee) -> bool:
    """
    كل موظف داخل نفس الشركة يمكنه رؤية جميع الموظفين.
    """
    if not user or not user.is_authenticated:
        return False

    return is_in_same_company(user, employee.company_id)


# ============================================================
#  Employee Edit Permissions
# ============================================================

def can_edit_employee(user, employee: Employee) -> bool:
    """
    HR → edit all
    Employee → edit self
    Manager → edit subordinate
    Chain manager → edit subordinate of subordinate
    """
    if not user or not user.is_authenticated:
        return False

    # HR
    if user_is_hr_manager(user):
        return True

    me = get_employee(user)
    if not me:
        return False

    # Employee edits himself
    if me.id == employee.id:
        return True

    # Direct manager
    if is_manager_of(user, employee):
        return True

    # Any manager in the chain
    if user_is_in_manager_chain(user, employee):
        return True

    return False
