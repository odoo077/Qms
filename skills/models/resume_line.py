# skills/models/resume_line.py
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from base.models.mixins import TimeStamped, UserStamped
from .resume_line_type import HrResumeLineType


class HrResumeLine(TimeStamped, UserStamped, models.Model):
    """
    Odoo-like hr.resume.line
    - سطر في CV لموظف (خبرة/تعليم/دورة).
    - company/department تُملآن تلقائيًا من employee عند الحفظ (للتوافق مع تقارير الشركة).
    """
    employee = models.ForeignKey("hr.Employee", on_delete=models.CASCADE, related_name="resume_lines")

    # denorm خفيف للتصفية/التقارير؛ نُحدّثها من employee في save()
    company = models.ForeignKey("base.Company", on_delete=models.PROTECT, related_name="resume_lines", null=True, blank=True)
    department = models.ForeignKey("hr.Department", on_delete=models.SET_NULL, related_name="resume_lines", null=True, blank=True)

    name = models.CharField(max_length=255, help_text="Title of the experience/course/education item.")
    line_type = models.ForeignKey(HrResumeLineType, on_delete=models.PROTECT, related_name="resume_lines")

    date_start = models.DateField(null=True, blank=True)
    date_end = models.DateField(null=True, blank=True)

    # ملاحظات/تفاصيل (يمكن جعلها HTML في الواجهة)
    description = models.TextField(blank=True)

    # خصائص إضافية حسب تعريف النوع (اختياري)
    properties = models.JSONField(default=dict, blank=True)

    # دورات تدريبية:
    COURSE_TYPES = (
        ("external", "External"),
        ("internal", "Internal"),
    )
    course_type = models.CharField(max_length=16, choices=COURSE_TYPES, default="external")
    external_url = models.URLField(blank=True)

    # شهادة/ملف مرفق اختياري
    certificate_file = models.FileField(upload_to="resume_certificates/", null=True, blank=True)
    certificate_filename = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "hr_resume_line"
        ordering = ("-date_start", "-date_end", "id")
        indexes = [
            models.Index(fields=["employee"]),
            models.Index(fields=["line_type"]),
            models.Index(fields=["date_start", "date_end"]),
        ]

    @property
    def is_course(self) -> bool:
        return bool(self.line_type and self.line_type.is_course)

    def clean(self):
        super().clean()
        # تحقق تواريخ
        if self.date_start and self.date_end and self.date_start > self.date_end:
            raise ValidationError({"date_end": "End date must be on or after start date."})
        # إن لم تكن دورة خارجية → امسح رابط external_url
        if self.course_type != "external" and self.external_url:
            self.external_url = ""

    def save(self, *args, **kwargs):
        # توليد اسم من الـ URL إن الاسم فارغ ولدينا external_url
        if not self.name and self.external_url:
            try:
                from urllib.parse import urlparse
                host = urlparse(self.external_url).netloc
                self.name = host or "External Course"
            except Exception:
                pass

        # company/department من الموظف
        if self.employee_id:
            self.company = self.employee.company
            self.department = self.employee.department

        # حفظ اسم الملف لو تم رفع مرفق
        if self.certificate_file and not self.certificate_filename:
            self.certificate_filename = getattr(self.certificate_file, "name", "") or ""

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.employee.name} · {self.name}"
