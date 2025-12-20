# skills/access.py
# ============================================================
# ACL definitions for Skills App (FINAL – 100% COMPATIBLE)
#
# Object-level ACL is applied ONLY on:
#   - EmployeeSkill
#   - ResumeLine
#
# Master data (SkillType, SkillLevel, Skill, ResumeLineType)
# do NOT receive object-level ACL.
#
# ACL Rules (fully aligned with base + hr):
#   1) HR Managers  → Full access.
#   2) Employee     → View + Change his own records.
#   3) Managers     → View + Change records of employees they are
#                     allowed to manage according to hr.access logic.
#   4) Others       → No access.
#
# ACL is stored using base.acl_service.grant_access
# ============================================================

from __future__ import annotations

from django.contrib.auth.models import Group
from django.apps import apps

from base.acl_service import grant_access
from hr.access import can_view_employee, can_edit_employee

# Lazy model loading (no hard dependency at import time)
Employee = apps.get_model("hr", "Employee")
EmployeeSkill = apps.get_model("skills", "EmployeeSkill")
ResumeLine = apps.get_model("skills", "ResumeLine")


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def _get_employee_by_user(user):
    """Return Employee linked to the given user, if any."""
    if not user or not user.is_authenticated:
        return None
    return Employee.objects.filter(user=user).first()


def _user_is_hr(user):
    """Check whether the user belongs to HR Managers group."""
    if not user or not user.is_authenticated:
        return False
    return user.groups.filter(name="HR Managers").exists()

