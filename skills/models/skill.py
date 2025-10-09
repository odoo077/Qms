# skills/models/skill.py
from django.db import models
from base.models.mixins import TimeStamped, UserStamped, ActivableMixin
from .skill_type import HrSkillType


class HrSkill(ActivableMixin, TimeStamped, UserStamped, models.Model):
    """
    Odoo-like hr.skill
    - مهارة مرتبطة بنوع.
    - color يُعرض من النوع (property للعرض كما في related).
    """
    name = models.CharField(max_length=255)
    sequence = models.IntegerField(default=10)
    skill_type = models.ForeignKey(HrSkillType, on_delete=models.CASCADE, related_name="skills")

    class Meta:
        db_table = "hr_skill"
        ordering = ("sequence", "name")
        unique_together = (("skill_type", "name"),)
        indexes = [
            models.Index(fields=["active"]),
            models.Index(fields=["skill_type"]),
        ]

    @property
    def color(self) -> int:
        return self.skill_type.color if self.skill_type_id else 1

    def __str__(self):
        return f"{self.name} ({self.skill_type.name})"
