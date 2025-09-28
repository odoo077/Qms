from django.db import models, transaction
from django.core.exceptions import ValidationError
from datetime import date, timedelta
from .mixins import TimeStamped
from .skill_type import HrSkillType
from .skill_level import HrSkillLevel
from .skill import HrSkill

class HrIndividualSkillMixin(TimeStamped):
    """
    Odoo-like individual skill mixin (versioned skills/certifications).
    يطبّق:
      - skill_type / skill / skill_level
      - valid_from / valid_to
      - is_certification (من skill_type)
      - قيد عدم التداخل (skills) والسماح بتعدد الشهادات ضمن مدى زمني مختلف
      - الأرشفة عند التعديل (turn write into archive+create)
    """
    class Meta:
        abstract = True
        ordering = ["skill_type_id", "skill_level_id"]

    # linked field يحدده النموذج الوارث (employee في HrEmployeeSkill)
    def _linked_field_name(self):
        raise NotImplementedError

    # الحقول الأساسية
    skill_type = models.ForeignKey(HrSkillType, on_delete=models.CASCADE)
    skill = models.ForeignKey(HrSkill, on_delete=models.CASCADE)
    skill_level = models.ForeignKey(HrSkillLevel, on_delete=models.CASCADE)

    valid_from = models.DateField(default=date.today)
    valid_to = models.DateField(null=True, blank=True)

    @property
    def is_certification(self):
        return bool(self.skill_type and self.skill_type.is_certification)

    @property
    def level_progress(self):
        return self.skill_level.level_progress if self.skill_level_id else None

    def clean(self):
        super().clean()
        # 1) type/skill/level consistency
        if self.skill_id and self.skill_type_id and self.skill.skill_type_id != self.skill_type_id:
            raise ValidationError({"skill": "Skill and skill type don't match."})
        if self.skill_level_id and self.skill_type_id and self.skill_level.skill_type_id != self.skill_type_id:
            raise ValidationError({"skill_level": "Skill level doesn't belong to selected skill type."})
        # 2) dates order
        if self.valid_to and self.valid_from and self.valid_to < self.valid_from:
            raise ValidationError({"valid_to": "The stop date cannot be before the start date."})
        # 3) overlap constraint
        linked_field = self._linked_field_name()
        filt = {
            f"{linked_field}_id": getattr(self, f"{linked_field}_id"),
            "skill_id": self.skill_id,
        }
        qs = self.__class__.objects.filter(**filt).exclude(pk=self.pk)
        if self.is_certification:
            # نفس skill و level و نفس المدى الزمني بالضبط ممنوع (عند السماح بتعديل المدى)
            same = qs.filter(skill_level_id=self.skill_level_id,
                             valid_from=self.valid_from,
                             valid_to=self.valid_to)
            if same.exists():
                raise ValidationError("Duplicate certification with same level and validity.")
        else:
            # لا يسمح بتداخل المدد لنفس skill
            for rec in qs:
                start1, end1 = self.valid_from, self.valid_to
                start2, end2 = rec.valid_from, rec.valid_to
                end1 = end1 or date.max
                end2 = end2 or date.max
                if max(start1, start2) <= min(end1, end2):
                    raise ValidationError("Overlapping skill validity for the same skill is not allowed.")

    # --- منطق الأرشفة عند التغيير (تبسيط مقابل write-command في Odoo) ---
    def save(self, *args, **kwargs):
        linked_field = self._linked_field_name()
        # تحديث قياسي
        is_update = bool(self.pk)
        if not is_update:
            return super().save(*args, **kwargs)

        # عند تعديل أي من (linked, skill, level, type) على سجل فعّال:
        old = self.__class__.objects.get(pk=self.pk)
        core_changed = (
            getattr(old, f"{linked_field}_id") != getattr(self, f"{linked_field}_id")
            or old.skill_id != self.skill_id
            or old.skill_level_id != self.skill_level_id
            or old.skill_type_id != self.skill_type_id
        )
        if not core_changed:
            return super().save(*args, **kwargs)

        # بدلاً من تعديل السجل: أرشف القديم وأنشئ سجلًا جديدًا
        with transaction.atomic():
            # أرشفة القديم إن لم يكن منتهي الصلاحية
            yesterday = date.today() - timedelta(days=1)
            if not old.valid_to or old.valid_to > yesterday:
                old.valid_to = yesterday
                super(self.__class__, old).save(update_fields=["valid_to"])
            # أنشئ جديدًا بالقيم الحالية
            new = self.__class__(
                **{
                    f"{linked_field}_id": getattr(self, f"{linked_field}_id"),
                    "skill_type": self.skill_type,
                    "skill": self.skill,
                    "skill_level": self.skill_level,
                    "valid_from": date.today() if not self.is_certification else (self.valid_from or date.today()),
                    "valid_to": None if not self.is_certification else self.valid_to,
                }
            )
            super(self.__class__, new).save()
            # لا نكمل حفظ السجل القديم المتغير
            return
