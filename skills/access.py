# skills/access.py
# ============================================================
# ACL definitions for Skills App (FULL & ODOO-LIKE)
#
# Applies per-object ACL ONLY on:
#     - EmployeeSkill       (hr.employee.skill)
#     - ResumeLine          (hr.resume.line)
#
# Master data (SkillType, SkillLevel, Skill, ResumeLineType)
# do NOT receive object-level ACL.
#
# ACL Rules:
#   1) HR Managers  → Full access to all employee skills & resume lines.
#   2) Employee     → View+Change his own EmployeeSkill / ResumeLine.
#   3) Managers     → View+Change for all subordinate employees
#                     based on hierarchical department tree.
#   4) Others       → No access unless explicitly granted.
#
# ACL stored using base.acl_service.grant_access
# ============================================================

from __future__ import annotations

from django.contrib.auth.models import Group
from base.acl_service import grant_access
from hr.models import Employee, Department
from skills.models import EmployeeSkill, ResumeLine


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def _get_employee_by_user(user):
    """Return the Employee record linked to this user (if any)."""
    try:
        return Employee.objects.filter(user=user).first()
    except Exception:
        return None


def _get_all_managed_departments(base_dept: Department):
    """
    Return all descendant departments including the base department itself.
    Uses parent_path just like Odoo's hierarchy model.
    """
    if not base_dept or not base_dept.parent_path:
        return Department.objects.none()

    return Department.objects.filter(parent_path__startswith=base_dept.parent_path)


def _user_is_hr(user):
    """Check if user is in HR Managers group."""
    return user.groups.filter(name="HR Managers").exists()


# ------------------------------------------------------------
# Core ACL Application Logic
# ------------------------------------------------------------

def apply_default_acl(obj):
    """
    Apply ACL for objects of:
        - EmployeeSkill
        - ResumeLine

    NOTE:
        'Skill' objects do NOT get ACL.
        Only employee-related records receive ACL.
    """

    if not obj.pk:
        # ACL can only be applied once object has a primary key.
        return

    # --------------------------------------------------------
    # 1) HR Managers → Full Access
    # --------------------------------------------------------
    try:
        hr_group = Group.objects.get(name="HR Managers")
        grant_access(
            obj,
            group=hr_group,
            view=True,
            change=True,
            delete=True,
            approve=True,
            assign=True,
            share=True,
        )
    except Group.DoesNotExist:
        # group not created yet
        pass

    # --------------------------------------------------------
    # Objects that belong to an employee
    # --------------------------------------------------------
    if isinstance(obj, (EmployeeSkill, ResumeLine)):

        employee = getattr(obj, "employee", None)
        if not employee:
            return

        # =========================================
        # 2) Employee → Access to his own records
        # =========================================
        if employee.user:
            grant_access(
                obj,
                user=employee.user,
                view=True,
                change=True,      # employee can edit his own skills/resume
                delete=False,
                approve=False,
                assign=False,
                share=False,
            )

        # =========================================
        # 3) Managers (hierarchical) → access to employees below them
        # =========================================

        # Find department of this employee
        dept = employee.department
        if not dept:
            return

        # Get all ancestors / same-path departments
        managed_depts = _get_all_managed_departments(dept)

        # For each department in path → its manager gets ACL
        for d in managed_depts:
            manager = getattr(d, "manager", None)
            manager_user = getattr(manager, "user", None) if manager else None

            if manager_user:
                grant_access(
                    obj,
                    user=manager_user,
                    view=True,
                    change=True,   # managers can update subordinate records
                    delete=False,
                    approve=False,
                    assign=False,
                    share=False,
                )

    # END
