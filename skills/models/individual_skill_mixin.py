# skills/models/individual_skill_mixin.py
from django.db import models
from django.core.exceptions import ValidationError
from base.models.mixins import TimeStamped, UserStamped
from .skill_type import HrSkillType
from .skill import HrSkill
from .skill_level import HrSkillLevel


class HrIndividualSkillMixin(TimeStamped, UserStamped, models.Model):
    """
    Abstract mixin (Odoo-like hr.individual.skill.mixin)
    يحتوي المنطق المشترك:
    - skill_type / skill / skill_level
    - valid_from / valid_to
    - خصائص related: is_certification, level_progress, color
    * تحقق أساسي على التواريخ؛
      منطق منع التداخل لغير الشهادات يُنفَّذ عبر signal/manager خارج هذا الموديل.
    """
    class Meta:
        abstract = True

    skill_type = models.ForeignKey(HrSkillType, on_delete=models.PROTECT, related_name="%(class)s_records")
    skill = models.ForeignKey(HrSkill, on_delete=models.PROTECT, related_name="%(class)s_records")
    skill_level = models.ForeignKey(HrSkillLevel, on_delete=models.PROTECT, related_name="%(class)s_records")

    valid_from = models.DateField()
    valid_to = models.DateField(null=True, blank=True)

    def clean(self):
        super().clean()
        # المهارة والمستوى يجب أن يتبعا نفس النوع
        if self.skill_id and self.skill_type_id and self.skill.skill_type_id != self.skill_type_id:
            raise ValidationError({"skill": "Skill must belong to the selected skill type."})
        if self.skill_level_id and self.skill_type_id and self.skill_level.skill_type_id != self.skill_type_id:
            raise ValidationError({"skill_level": "Level must belong to the selected skill type."})
        # valid_from <= valid_to
        if self.valid_to and self.valid_from and self.valid_from > self.valid_to:
            raise ValidationError({"valid_to": "valid_to must be on or after valid_from."})

    # === Related-style properties (عرض فقط) ===
    @property
    def is_certification(self) -> bool:
        return bool(self.skill_type and self.skill_type.is_certification)

    @property
    def level_progress(self) -> int:
        return self.skill_level.level_progress if self.skill_level_id else 0

    @property
    def color(self) -> int:
        return self.skill_type.color if self.skill_type_id else 1
