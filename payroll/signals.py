# -*- coding: utf-8 -*-
"""
Signals — إعادة تجميع القسيمة بعد تعديل/حذف أي سطر.
"""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

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

