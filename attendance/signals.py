from datetime import date
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from .models import AttendanceLog
from .services import rebuild_attendance_day
from hr.models import EmployeeSchedule, EmployeeDayOff, WorkShiftRule

def _rebuild_for_instance(employee_id, dt):
    try:
        rebuild_attendance_day(employee_id, dt)
    except Exception:
        pass  # لا نكسر الطلب الإداري

@receiver(post_save, sender=AttendanceLog)
@receiver(post_delete, sender=AttendanceLog)
def _rebuild_on_log(sender, instance, **kwargs):
    _rebuild_for_instance(instance.employee_id, instance.ts.date())

@receiver(post_save, sender=EmployeeDayOff)
@receiver(post_delete, sender=EmployeeDayOff)
def _rebuild_on_dayoff(sender, instance, **kwargs):
    _rebuild_for_instance(instance.employee_id, instance.date)

@receiver(post_save, sender=EmployeeSchedule)
@receiver(post_delete, sender=EmployeeSchedule)
def _rebuild_on_schedule(sender, instance, **kwargs):
    # أعد بناء أول يوم من الفترة (غالبًا سيُستدعى لاحقًا عبر الأتمتة اليومية)
    _rebuild_for_instance(instance.employee_id, instance.date_from)

@receiver(post_save, sender=WorkShiftRule)
def _rebuild_on_shift_rule(sender, instance, **kwargs):
    # لا نعرف الموظفين مباشرة؛ يُكفى بإعادة حساب الأيام عند أول حدث/طلب أو عبر job لاحقًا
    pass
