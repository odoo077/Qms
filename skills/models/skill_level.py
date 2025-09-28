from django.db import models
from django.core.exceptions import ValidationError
from .mixins import TimeStamped
from .skill_type import HrSkillType

class HrSkillLevel(TimeStamped):
    skill_type = models.ForeignKey(HrSkillType, on_delete=models.CASCADE, related_name="skill_level_ids")
    name = models.CharField(max_length=255)
    level_progress = models.IntegerField(help_text="Progress 0..100")
    default_level = models.BooleanField(default=False)

    # حقل مساعد (غير مخزّن في Odoo؛ هنا نتركه فعّالًا إن أردت)
    technical_is_new_default = models.BooleanField(default=False)

    class Meta:
        db_table = "hr_skill_level"
        ordering = ["level_progress"]

    def clean(self):
        super().clean()
        if self.level_progress < 0 or self.level_progress > 100:
            raise ValidationError({"level_progress": "Progress should be between 0 and 100."})

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.default_level:
            # ألغِ default عن باقي المستويات لنفس النوع
            HrSkillLevel.objects.filter(skill_type=self.skill_type).exclude(pk=self.pk).update(default_level=False)
