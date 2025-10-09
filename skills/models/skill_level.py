# skills/models/skill_level.py
from django.db import models
from django.core.exceptions import ValidationError
from base.models.mixins import TimeStamped, UserStamped
from .skill_type import HrSkillType


class HrSkillLevel(TimeStamped, UserStamped, models.Model):
    """
    Odoo-like hr.skill.level
    - مستوى تابع لنوع مهارة واحد.
    - default_level: يجب أن يكون واحدًا فقط لكل SkillType (ن enforced في save()).
    """
    skill_type = models.ForeignKey(HrSkillType, on_delete=models.CASCADE, related_name="skill_levels")
    name = models.CharField(max_length=255)
    level_progress = models.PositiveIntegerField(default=0)  # 0..100
    default_level = models.BooleanField(default=False)

    class Meta:
        db_table = "hr_skill_level"
        ordering = ("level_progress", "id")
        unique_together = (("skill_type", "name"),)
        indexes = [
            models.Index(fields=["skill_type"]),
            models.Index(fields=["level_progress"]),
        ]
        constraints = [
            models.CheckConstraint(
                name="skill_level_progress_range",
                check=models.Q(level_progress__gte=0) & models.Q(level_progress__lte=100),
            )
        ]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # enforce "one default per type"
        if self.default_level:
            (type(self).objects
             .filter(skill_type=self.skill_type)
             .exclude(pk=self.pk)
             .update(default_level=False))

    def __str__(self):
        return f"{self.skill_type.name}: {self.name} ({self.level_progress}%)"
