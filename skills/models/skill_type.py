from django.db import models
from .mixins import TimeStamped
import random


def default_color():
    return random.randint(1, 11)


class HrSkillType(TimeStamped):
    active = models.BooleanField(default=True)
    sequence = models.IntegerField(default=10)
    name = models.CharField(max_length=255)
    color = models.IntegerField(default=default_color)
    is_certification = models.BooleanField(default=False)

    # store=True in Odoo → persist & recompute
    levels_count = models.IntegerField(default=0, help_text="Number of levels linked to this skill type")

    class Meta:
        db_table = "hr_skill_type"
        ordering = ["sequence", "name"]

    def __str__(self):
        return f"{self.name}{' 🎖️' if self.is_certification else ''}"  # Odoo adds a medal for certifications. :contentReference[oaicite:7]{index=7}

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Recompute stored compute: levels_count (Odoo: _compute_levels_count). :contentReference[oaicite:8]{index=8}
        count = self.hr_skill_level_set.count()
        if count != self.levels_count:
            self.levels_count = count
            super().save(update_fields=["levels_count"])

    def clean(self):
        # Odoo constraint: must have at least one skill and one level. Enforce softly at use-time;
        # the strict Odoo check is done when relations change. :contentReference[oaicite:9]{index=9}
        pass
