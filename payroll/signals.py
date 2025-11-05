# -*- coding: utf-8 -*-
"""
Signals — إعادة تجميع القسيمة بعد تعديل/حذف أي سطر.
"""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from . import models as m
from base.acl_service import apply_default_acl
# ✅ مهم: استيراد PayslipLine لمنع Unresolved reference
from .models import PayslipLine


@receiver(post_save, sender=PayslipLine)
def _recompute_after_line_save(sender, instance, **kwargs):
    slip = instance.payslip
    if getattr(slip, "id", None):
        slip.recompute(persist=True)

@receiver(post_delete, sender=PayslipLine)
def _recompute_after_line_delete(sender, instance, **kwargs):
    slip = instance.payslip
    if getattr(slip, "id", None):
        slip.recompute(persist=True)



# ==========================================================
# Default ACLs for payroll objects
# ==========================================================
@receiver(post_save, sender=m.PayrollPeriod)
@receiver(post_save, sender=m.Payslip)
@receiver(post_save, sender=m.EmployeeSalary)
def _apply_default_acl_payroll(sender, instance, created, **kwargs):
    if created:
        apply_default_acl(instance)
