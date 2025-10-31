from datetime import datetime, date, time, timedelta
from django.db import transaction, models
from django.utils import timezone

from hr.models import Employee, WorkShiftRule
from .models import AttendanceLog, AttendanceDay

def _local_daterange(dt_from: datetime, dt_to: datetime):
    """يقسّم الفترة إلى تواريخ محلية (helper بسيط)."""
    d = dt_from.date()
    while d <= dt_to.date():
        yield d
        d += timedelta(days=1)

def _planned_window(employee: Employee, the_date: date):
    """
    استخرج إطار الدوام المخطَّط لذلك اليوم من الشفت الحالي:
    (start, end, is_weekend, shift_name)
    """
    shift = employee.current_shift_on(the_date)
    if not shift:
        return None, None, False, None

    weekday = the_date.weekday()  # 0..6
    rule = WorkShiftRule.objects.filter(shift=shift, weekday=weekday).order_by("start_time").first()
    if not rule:
        # لا توجد قاعدة لليوم => ويكند
        return None, None, True, shift.name
    return rule.start_time, rule.end_time, False, shift.name

def _pair_logs(logs):
    """
    ازواج IN/OUT بترتيب زمني. إن لم يوجد OUT يقف على آخر اليوم.
    """
    ins, outs = [], []
    for ev in logs:
        (ins if ev.kind == "in" else outs).append(ev.ts)
    pairs = []
    while ins:
        start = ins.pop(0)
        if outs:
            end = outs.pop(0)
            if end < start:
                # سهم مكسور: تجاهله في التجميع
                continue
        else:
            end = start  # لا OUT: نعطي صفر دقائق (سنسجل ملاحظة)
        pairs.append((start, end))
    return pairs

@transaction.atomic
def rebuild_attendance_day(employee_id: int, the_date: date):
    """
    يحسب AttendanceDay من الصفر لذلك الموظف/اليوم.
    - يعتمد على الشفت، أيام العطل الفردية، وLogs اليوم.
    """
    emp = Employee.objects.select_related("company").get(pk=employee_id)
    company = emp.company

    pstart, pend, is_weekend, shift_name = _planned_window(emp, the_date)
    is_day_off = emp.is_day_off(the_date)

    # اجمع أحداث ذلك اليوم (حسب المنطقة الزمنية للشركة لاحقًا)
    logs = AttendanceLog.objects.filter(employee=emp, ts__date=the_date).order_by("ts")

    first_in, last_out = None, None
    worked = 0
    notes = {}

    pairs = _pair_logs(list(logs))
    if pairs:
        first_in = pairs[0][0]
        last_out = pairs[-1][1]
        for s, e in pairs:
            delta = max(0, int((e - s).total_seconds() // 60))
            worked += delta
        if any(s == e for s, e in pairs):
            notes["open_interval"] = True

    # حساب التأخير/الخروج المبكر/الوقت الإضافي إن وُجدت نافذة مخططة
    late = early = overtime = 0
    if pstart and pend:
        # حوّل أوقات planned إلى datetime بنفس تاريخ اليوم
        dt_start = timezone.make_aware(datetime.combine(the_date, pstart))
        dt_end   = timezone.make_aware(datetime.combine(the_date, pend))
        if first_in:
            late = max(0, int((first_in - dt_start).total_seconds() // 60))
        if last_out:
            early = max(0, int((dt_end - last_out).total_seconds() // 60))
        # وقت إضافي = (العمل - طول النافذة)، نضيف الاستراحة لاحقًا إن أردت
        planned_len = int((dt_end - dt_start).total_seconds() // 60)
        overtime = worked - planned_len

    # تحديد الحالة
    if is_day_off:
        status = "leave"
    elif is_weekend and not pstart:
        status = "weekend"
    elif not pstart and not logs.exists():
        status = "no_schedule"
    elif worked == 0:
        status = "absent"
    elif late > 0 or early > 0:
        status = "partial"
    else:
        status = "present"

    obj, _ = AttendanceDay.objects.update_or_create(
        employee=emp, date=the_date,
        defaults=dict(
            company=company,
            shift_name=shift_name or "",
            weekday=the_date.weekday(),
            planned_from=pstart, planned_to=pend,
            first_in=first_in, last_out=last_out,
            worked_minutes=max(0, worked),
            late_minutes=max(0, late),
            early_leave_minutes=max(0, early),
            overtime_minutes=overtime,
            is_weekend=is_weekend,
            is_day_off=is_day_off,
            status=status,
            calc_notes=notes,
        )
    )
    return obj
