# payroll/signals.py

"""
Signals — Payroll app

Responsibilities:
- Recompute Payslip totals after any PayslipLine change (create/update/delete).
- Apply default ACL (base.apply_default_acl) for newly created payroll objects.

Notes:
- Recompute is allowed ONLY while Payslip is in draft (models.py enforces this).
- Signals must never break the save/delete path; therefore recompute is guarded.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from base.acl_service import apply_default_acl
from . import models as m

# ✅ Important: keep explicit import to avoid "Unresolved reference" in some IDEs
from .models import PayslipLine


# ==========================================================
# Payslip recompute (Lines lifecycle)
# ==========================================================

def _safe_recompute_payslip(slip: "m.Payslip") -> None:
    """
    Recompute totals safely:
    - Only draft payslips can be recomputed (enforced by Payslip.recompute()).
    - Never raise from signal handlers.
    """
    if not slip or not getattr(slip, "pk", None):
        return

    # Payslip.recompute() now blocks non-draft, so we must guard here.
    if getattr(slip, "state", None) != "draft":
        return

    try:
        slip.recompute(persist=True)
    except ValidationError:
        # Should not break the save/delete path.
        return
    except Exception:
        # Defensive: signals must not crash writes.
        return


@receiver(post_save, sender=PayslipLine)
def _recompute_after_line_save(sender, instance: PayslipLine, **kwargs):
    slip = getattr(instance, "payslip", None)
    _safe_recompute_payslip(slip)


@receiver(post_delete, sender=PayslipLine)
def _recompute_after_line_delete(sender, instance: PayslipLine, **kwargs):
    slip = getattr(instance, "payslip", None)
    _safe_recompute_payslip(slip)


# ==========================================================
# Default ACLs for payroll objects
# ==========================================================

@receiver(post_save, sender=m.PayrollPeriod)
@receiver(post_save, sender=m.Payslip)
@receiver(post_save, sender=m.PayslipLine)
@receiver(post_save, sender=m.EmployeeSalary)
@receiver(post_save, sender=m.PayrollStructure)
@receiver(post_save, sender=m.SalaryRuleCategory)
@receiver(post_save, sender=m.RuleParameter)
@receiver(post_save, sender=m.SalaryRule)
@receiver(post_save, sender=m.InputType)
@receiver(post_save, sender=m.PayslipInput)
def _apply_default_acl_payroll(sender, instance, created, **kwargs):
    """
    Apply base default ACL only on creation.
    This keeps payroll models consistent with the global ACL system.
    """
    if created:
        apply_default_acl(instance)
