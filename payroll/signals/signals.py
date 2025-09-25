# payroll/signals.py
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import PayslipLine, Payslip


@receiver(post_save, sender=PayslipLine)
def _recompute_after_line_save(sender, instance, **kwargs):
    # Avoid recursion: recompute on parent, not saving the line again
    slip = instance.payslip
    if slip_id := getattr(slip, "id", None):
        slip.recompute(save=True)


@receiver(post_delete, sender=PayslipLine)
def _recompute_after_line_delete(sender, instance, **kwargs):
    slip = instance.payslip
    if slip_id := getattr(slip, "id", None):
        slip.recompute(save=True)