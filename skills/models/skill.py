from django.db import models
from .mixins import TimeStamped
from .skill_type import HrSkillType

class HrSkill(TimeStamped):
    name = models.CharField(max_length=255)
    sequence = models.IntegerField(default=10)
    skill_type = models.ForeignKey(HrSkillType, on_delete=models.CASCADE, related_name="skills")

    class Meta:
        db_table = "hr_skill"
        ordering = ["sequence", "name"]

    def __str__(self):
        return self.name

    @property
    def color(self) -> int:
        # Related to type's color in Odoo. :contentReference[oaicite:14]{index=14}
        return self.skill_type.color if self.skill_type_id else 0
