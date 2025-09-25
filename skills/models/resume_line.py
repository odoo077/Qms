import re
from django.db import models
from django.core.exceptions import ValidationError
from .mixins import TimeStamped
from hr.models import Employee
from .resume_line_type import HrResumeLineType


class HrResumeLine(TimeStamped):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="resume_lines", db_index=True)
    # avatar_128/company/department can be derived via employee relations (display-time), as in Odoo relateds. :contentReference[oaicite:28]{index=28}

    name = models.CharField(max_length=255)
    date_start = models.DateField()
    date_end = models.DateField(null=True, blank=True)
    duration = models.IntegerField(default=0)  # optional cache
    description = models.TextField(blank=True)  # HTML in Odoo

    line_type = models.ForeignKey(HrResumeLineType, on_delete=models.SET_NULL, null=True, related_name="resume_lines")
    # is_course is related in Odoo; we expose as a property. :contentReference[oaicite:29]{index=29}
    @property
    def is_course(self) -> bool:
        return bool(self.line_type and self.line_type.is_course)

    COURSE_TYPES = [("external", "External")]
    course_type = models.CharField(max_length=20, choices=COURSE_TYPES, default="external")

    # Odoo computes color/external_url from course_type; keep same semantics. :contentReference[oaicite:30]{index=30}
    color = models.CharField(max_length=7, default="#000000")
    external_url = models.CharField(max_length=1024, blank=True)

    certificate_filename = models.CharField(max_length=255, blank=True)
    certificate_file = models.BinaryField(null=True, blank=True)

    # Odoo Properties mapped to JSON; validated against type’s definition at the service layer. :contentReference[oaicite:31]{index=31}
    resume_line_properties = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "hr_resume_line"
        ordering = ["line_type_id", "-date_end", "-date_start"]
        constraints = [
            models.CheckConstraint(
                check=(models.Q(date_end__isnull=True) | models.Q(date_start__lte=models.F("date_end"))),
                name="chk_resume_line_dates_order"  # :contentReference[oaicite:32]{index=32}
            )
        ]

    def clean(self):
        super().clean()
        if self.date_end and self.date_start and self.date_start > self.date_end:
            raise ValidationError("The start date must be anterior to the end date.")  # :contentReference[oaicite:33]{index=33}

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # compute: external_url only for 'external'
        if self.course_type != "external" and self.external_url:
            self.external_url = ""
        # compute: color based on course_type
        self.color = "#a2a2a2" if self.course_type == "external" else self.color  # :contentReference[oaicite:34]{index=34}
        # onchange: auto name from URL host if name is empty and URL set. :contentReference[oaicite:35]{index=35}
        if not self.name and self.external_url:
            m = re.search(r"((https|http):\/\/)?(www\.)?(.*)\.", self.external_url)
            if m:
                self.name = (m.group(4) or "").capitalize()
        super().save(update_fields=["external_url", "color", "name"])
