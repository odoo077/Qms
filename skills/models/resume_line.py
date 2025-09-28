import re
from django.db import models
from django.core.exceptions import ValidationError
from .mixins import TimeStamped
from hr.models import Employee
from .resume_line_type import HrResumeLineType

class HrResumeLine(TimeStamped):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="resume_lines", db_index=True)
    name = models.CharField(max_length=255)
    date_start = models.DateField()
    date_end = models.DateField(null=True, blank=True)
    duration = models.IntegerField(default=0)
    description = models.TextField(blank=True)  # Odoo يستخدم Html

    line_type = models.ForeignKey(HrResumeLineType, on_delete=models.SET_NULL, null=True, blank=True, related_name="resume_lines")
    # is_course related:
    @property
    def is_course(self):
        return bool(self.line_type and self.line_type.is_course)

    COURSE_EXTERNAL = "external"
    course_type = models.CharField(max_length=16, choices=[(COURSE_EXTERNAL, "External")], default=COURSE_EXTERNAL)

    color = models.CharField(max_length=7, default="#000000")
    external_url = models.CharField(max_length=512, blank=True)

    certificate_filename = models.CharField(max_length=255, blank=True)
    certificate_file = models.FileField(upload_to="hr/certificates/", null=True, blank=True)

    # بديل Properties (نخزّن القيم فعليًا هنا):
    resume_line_properties = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "hr_resume_line"
        ordering = ["line_type_id", "-date_end", "-date_start"]

    def clean(self):
        super().clean()
        if self.date_end and self.date_start and self.date_end < self.date_start:
            raise ValidationError({"date_end": "The start date must be anterior to the end date."})

    def save(self, *args, **kwargs):
        # ألوان بسيطة حسب course_type
        if self.course_type == self.COURSE_EXTERNAL:
            self.color = "#a2a2a2"
        else:
            self.color = "#000000"
        # smart name from external_url إذا لم يكن هناك name
        if not self.name and self.external_url:
            m = re.search(r"((https|http):\/\/)?(www\.)?([^\/\.]+)\.", self.external_url)
            if m:
                self.name = m.group(4).capitalize()
        return super().save(*args, **kwargs)
