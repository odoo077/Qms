from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.utils import timezone

# نعيد استخدام شفت/جداول الشفت/إجازات الموظف من HR
# hr.WorkShift / hr.WorkShiftRule / hr.EmployeeSchedule / hr.EmployeeDayOff
# ونستخدم Employee من hr
# Company من base

class AttendanceLog(models.Model):
    """
    حدث حضور خام: دخول أو خروج بوقت محدد.
    لاحقًا يمكن توسيع 'source' للبصمة/الموبايل/الويب.
    """
    KIND = [("in", "Check In"), ("out", "Check Out")]

    company  = models.ForeignKey("base.Company", on_delete=models.PROTECT, related_name="att_logs", db_index=True)
    employee = models.ForeignKey("hr.Employee",  on_delete=models.CASCADE, related_name="att_logs", db_index=True)

    kind      = models.CharField(max_length=8, choices=KIND)
    ts        = models.DateTimeField(help_text="Event timestamp in company timezone")
    source    = models.CharField(max_length=32, blank=True, default="manual")
    note      = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        db_table = "att_log"
        indexes = [
            models.Index(fields=["company", "employee", "ts"], name="attlog_c_e_ts_idx"),
            models.Index(fields=["employee", "ts"], name="attlog_e_ts_idx"),
        ]
        constraints = [
            models.CheckConstraint(name="attlog_kind_chk", check=models.Q(kind__in=["in", "out"])),
        ]
        ordering = ("employee_id", "ts")

    def clean(self):
        super().clean()
        # اتساق الشركة
        if self.employee_id and self.company_id and self.company_id != self.employee.company_id:
            raise ValidationError({"company": "Company must equal employee company."})

    def __str__(self):
        return f"{self.employee} · {self.kind} @ {self.ts}"


class AttendanceDay(models.Model):
    """
    تلخيص يومي مادي لكل موظف/تاريخ.
    يُعاد بناؤه تلقائيًا من AttendanceLog + HR shifts + Days Off.
    """
    STATUS = [
        ("absent", "Absent"),
        ("present", "Present"),
        ("partial", "Partial"),
        ("leave", "Leave/Day Off"),
        ("weekend", "Weekend"),
        ("no_schedule", "No Schedule"),
    ]

    company  = models.ForeignKey("base.Company", on_delete=models.PROTECT, related_name="att_days", db_index=True)
    employee = models.ForeignKey("hr.Employee",  on_delete=models.CASCADE, related_name="att_days", db_index=True)
    date     = models.DateField(db_index=True)

    # من الشفت النشط في ذلك اليوم
    shift_name   = models.CharField(max_length=255, blank=True)
    weekday      = models.PositiveSmallIntegerField(default=0)   # 0=Mon..6=Sun
    planned_from = models.TimeField(null=True, blank=True)
    planned_to   = models.TimeField(null=True, blank=True)

    # من الأحداث
    first_in     = models.DateTimeField(null=True, blank=True)
    last_out     = models.DateTimeField(null=True, blank=True)

    worked_minutes     = models.PositiveIntegerField(default=0)
    late_minutes       = models.PositiveIntegerField(default=0)
    early_leave_minutes= models.PositiveIntegerField(default=0)
    overtime_minutes   = models.IntegerField(default=0)  # قد يكون سالب/موجب (بالموجب: زيادة)

    is_weekend  = models.BooleanField(default=False)
    is_day_off  = models.BooleanField(default=False)  # من EmployeeDayOff
    status      = models.CharField(max_length=16, choices=STATUS, default="no_schedule", db_index=True)

    calc_notes  = models.JSONField(default=dict, blank=True)  # لأي تفاصيل/تحذيرات

    class Meta:
        db_table = "att_day"
        unique_together = [("employee", "date")]
        indexes = [
            models.Index(fields=["company", "employee", "date"], name="attday_c_e_d_idx"),
            models.Index(fields=["company", "date", "status"], name="attday_c_d_s_idx"),
        ]
        ordering = ("employee_id", "-date")

    def __str__(self):
        return f"{self.employee} · {self.date} [{self.status}]"
