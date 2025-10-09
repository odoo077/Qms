# skills/models/skill_type.py
from django.db import models
from django.core.exceptions import ValidationError
from base.models.mixins import TimeStamped, UserStamped, ActivableMixin


class HrSkillType(ActivableMixin, TimeStamped, UserStamped, models.Model):
    """
    Odoo-like hr.skill.type
    - يمسك مجموعة المهارات ومستوياتها.
    - يدعم وسم 'is_certification' لتمييز الشهادات.
    - levels_count: يُحدّث عبر إشارة (signal) بعد حفظ/حذف HrSkillLevel.
    """
    name = models.CharField(max_length=255, unique=True, db_index=True)
    sequence = models.IntegerField(default=10)
    color = models.IntegerField(default=1)  # 1..11 عادةً في Odoo
    is_certification = models.BooleanField(default=False)

    # يُحدَّث عبر signal (skills/signals/skill_signals.py)
    levels_count = models.PositiveIntegerField(default=0, editable=False)

    class Meta:
        db_table = "hr_skill_type"
        ordering = ("sequence", "name")
        indexes = [
            models.Index(fields=["active"]),
            models.Index(fields=["sequence", "name"]),
        ]

    def clean(self):
        super().clean()
        # ملاحظة: في Odoo يُرفض نوع بلا مهارات/مستويات عند عمليات معينة.
        # هنا نترك التحقق للواجهة/المنطق التطبيقي (أو تضيفه لاحقًا بعد توفّر بيانات كافية).

    def __str__(self):
        return f"{self.name}{' 🏅' if self.is_certification else ''}"
