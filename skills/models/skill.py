from django.db import models
from .mixins import TimeStamped
from .skill_type import HrSkillType

class HrSkill(TimeStamped):
    name = models.CharField(max_length=255)
    sequence = models.IntegerField(default=10)
    skill_type = models.ForeignKey(HrSkillType, on_delete=models.CASCADE, related_name="skill_ids")

    class Meta:
        db_table = "hr_skill"
        ordering = ["sequence", "name"]

    @property
    def color(self):
        # بديل related=skill_type.color
        return self.skill_type.color if self.skill_type_id else None
