from django.db import models
from django.core.exceptions import ValidationError
from .mixins import TimeStamped
from .skill_type import HrSkillType

class HrSkillLevel(TimeStamped):
    skill_type = models.ForeignKey(HrSkillType, on_delete=models.CASCADE, related_name="hr_skill_level_set")
    name = models.CharField(max_length=255)
    level_progress = models.IntegerField(help_text="0..100% mastery")
    default_level = models.BooleanField(default=False)

    # Frontend helper flag like Odoo's non-stored compute (we keep it writable). :contentReference[oaicite:10]{index=10}
    technical_is_new_default = models.BooleanField(default=False)

    class Meta:
        db_table = "hr_skill_level"
        ordering = ["level_progress"]
        constraints = [
            models.CheckConstraint(check=models.Q(level_progress__gte=0, level_progress__lte=100),
                                   name="chk_skill_level_progress_0_100"),  # :contentReference[oaicite:11]{index=11}
        ]

    def __str__(self):
        return f"{self.name} ({self.level_progress}%)"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # If this became default, clear others in same skill_type. (Odoo mirrors this behavior.) :contentReference[oaicite:12]{index=12}
        if self.default_level:
            self.skill_type.hr_skill_level_set.exclude(pk=self.pk).update(default_level=False)
        # Mark helper as reset (like Odoo's compute that resets). :contentReference[oaicite:13]{index=13}
        if self.technical_is_new_default:
            self.technical_is_new_default = False
            super().save(update_fields=["technical_is_new_default"])
        # Refresh skill_type levels_count
        self.skill_type.save()
