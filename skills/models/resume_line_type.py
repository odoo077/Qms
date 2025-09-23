from django.db import models
from .mixins import TimeStamped

class HrResumeLineType(TimeStamped):
    name = models.CharField(max_length=255)
    sequence = models.IntegerField(default=10)
    is_course = models.BooleanField(default=False)
    # Odoo PropertiesDefinition → use JSON schema-like dict here. :contentReference[oaicite:27]{index=27}
    resume_line_type_properties_definition = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "hr_resume_line_type"
        ordering = ["sequence"]

    def __str__(self):
        return self.name
