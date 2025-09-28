from django.db import models
from .mixins import TimeStamped

class HrResumeLineType(TimeStamped):
    name = models.CharField(max_length=255)
    sequence = models.IntegerField(default=10)
    is_course = models.BooleanField(default=False)
    # بديل PropertiesDefinition في Odoo: نخزن مخطط الخصائص كـ JSON إن رغبت
    resume_line_type_properties_definition = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "hr_resume_line_type"
        ordering = ["sequence"]
