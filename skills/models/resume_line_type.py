# skills/models/resume_line_type.py
from django.db import models
from django.contrib.postgres.fields import JSONField  # لو لم تكن على Postgres، استخدم models.JSONField
from base.models.mixins import TimeStamped, UserStamped, ActivableMixin


class HrResumeLineType(ActivableMixin, TimeStamped, UserStamped, models.Model):
    """
    Odoo-like hr.resume.line.type
    - تعريف أنواع أسطر السيرة (خبرة/تعليم/دورة...).
    - يمكن تعريف خصائص مخصّصة لكل نوع عبر JSON schema بسيط.
    """
    name = models.CharField(max_length=255, unique=True, db_index=True)
    sequence = models.IntegerField(default=10)
    is_course = models.BooleanField(default=False)

    # مخطط اختياري لخصائص سطر السيرة (قائمة مفاتيح/أنواع/إلزامية...)
    properties_definition = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "hr_resume_line_type"
        ordering = ("sequence", "name")
        indexes = [models.Index(fields=["active"]),]

    def __str__(self):
        return self.name
