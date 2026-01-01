# skills/signals.py
# ============================================================
# Signals for Skills app (FINAL – Delegates ACL to base)
#
# Responsibilities:
# - Capture old employee before save (for ACL transfer)
# - Delegate ALL object-level ACL to base.apply_default_acl
#
# IMPORTANT:
# - No direct ACL logic here
# - No grant/revoke calls
# - Matches hr.signals philosophy
# ============================================================

from __future__ import annotations

from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

from base.acl_service import apply_default_acl
from . import models



def _capture_old_employee(instance):
    if not instance.pk:
        instance._old_employee_id = None
        return

    try:
        old = instance.__class__.objects.only("employee_id").get(pk=instance.pk)
        instance._old_employee_id = old.employee_id
    except instance.__class__.DoesNotExist:
        instance._old_employee_id = None


# ============================================================
# EmployeeSkill
# ============================================================

@receiver(pre_save, sender=models.EmployeeSkill)
def employeeskill_capture_old_employee(sender, instance, **kwargs):
    _capture_old_employee(instance)



@receiver(post_save, sender=models.EmployeeSkill)
def employeeskill_apply_acl(sender, instance: models.EmployeeSkill, created: bool, **kwargs):
    """
    Delegate ACL handling to base.apply_default_acl.
    """
    apply_default_acl(
        instance,
        created=created,
        old_employee_id=getattr(instance, "_old_employee_id", None),
    )


# ============================================================
# ResumeLine
# ============================================================

@receiver(pre_save, sender=models.ResumeLine)
def resumeline_capture_old_employee(sender, instance, **kwargs):
    _capture_old_employee(instance)


@receiver(post_save, sender=models.ResumeLine)
def resumeline_apply_acl(sender, instance: models.ResumeLine, created: bool, **kwargs):
    """
    Delegate ACL handling to base.apply_default_acl.
    """
    apply_default_acl(
        instance,
        created=created,
        old_employee_id=getattr(instance, "_old_employee_id", None),
    )
