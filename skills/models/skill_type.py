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

    # علاقات عكسية قياسية (Odoo: one2many)
    # ستتعبأ تلقائيًا من HrSkill.skill_type و HrSkillLevel.skill_type
    # (لا نحتاج تعريف OneToMany صريح في Django)
    # levels_count (computed/store) سنحتسبه عند الحفظ
    levels_count = models.IntegerField(default=0)  # بديل store=True

    class Meta:
        db_table = "hr_skill_type"
        ordering = ["sequence", "name"]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # تحديث levels_count = عدد HrSkillLevel المرتبطة
        from .skill_level import HrSkillLevel
        cnt = HrSkillLevel.objects.filter(skill_type=self).count()
        if cnt != self.levels_count:
            HrSkillType.objects.filter(pk=self.pk).update(levels_count=cnt)
