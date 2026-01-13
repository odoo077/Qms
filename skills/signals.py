# skills/signals.py
# ============================================================
# Signals for Skills app (FINAL – NO ACL / NO PERMISSIONS)
#
# Responsibilities:
# - Keep signals minimal and deterministic
# - Handle ONLY data integrity helpers if needed
#
# Explicitly NOT responsible for:
# - Object-level permissions
# - View/Add/Edit/Delete access
# - ACL, Guardian, or role-based logic
#
# This file is intentionally lightweight.
# ============================================================

from __future__ import annotations

from django.db.models.signals import pre_save
from django.dispatch import receiver

from . import models


# ============================================================
# Internal helpers
# ============================================================

def _capture_old_employee(instance):
    """
    Capture previous employee_id before save.

    Purpose:
    - Data comparison
    - Auditing / future extensions
    - Safe to keep even without ACL

    NOTE:
    - No permissions logic
    - No side effects
    """
    if not instance.pk:
        instance._old_employee_id = None
        return

    try:
        old = instance.__class__.objects.only("employee_id").get(pk=instance.pk)
        instance._old_employee_id = old.employee_id
    except instance.__class__.DoesNotExist:
        instance._old_employee_id = None


# ============================================================
# EmployeeSkill Signals
# ============================================================

@receiver(pre_save, sender=models.EmployeeSkill)
def employeeskill_capture_old_employee(sender, instance, **kwargs):
    """
    Capture previous employee before saving EmployeeSkill.

    Safe:
    - No permissions
    - No writes
    """
    _capture_old_employee(instance)


# ============================================================
# ResumeLine Signals
# ============================================================

@receiver(pre_save, sender=models.ResumeLine)
def resumeline_capture_old_employee(sender, instance, **kwargs):
    """
    Capture previous employee before saving ResumeLine.

    Safe:
    - No permissions
    - No writes
    """
    _capture_old_employee(instance)
