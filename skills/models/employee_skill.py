# skills/models/employee_skill.py
from django.db import models
from django.utils import timezone
from django.db.models import Q
from base.models.mixins import TimeStamped, UserStamped
from .individual_skill_mixin import HrIndividualSkillMixin


class HrEmployeeSkill(HrIndividualSkillMixin, TimeStamped, UserStamped, models.Model):
    """
    Odoo-like hr.employee.skill
    يربط موظفًا بمهارة/مستوى/فترة.
    - منطق منع التداخل لغير الشهادات موجود في signal (employee_skill_signals.py).
    - وفّرنا مدير مساعد لإرجاع “المهارات الحالية” للموظف.
    """
    employee = models.ForeignKey("hr.Employee", on_delete=models.CASCADE, related_name="skills")

    class Meta:
        db_table = "hr_employee_skill"
        ordering = ("skill_type", "skill", "skill_level", "valid_from", "id")
        indexes = [
            models.Index(fields=["employee"]),
            models.Index(fields=["skill"]),
            models.Index(fields=["skill_type"]),
            models.Index(fields=["skill_level"]),
        ]
        # لا نضع unique_together صارمًا لأن الشهادات قد تتكرر بفترات مختلفة.

    def __str__(self):
        return f"{self.employee.name} · {self.skill.name} ({self.skill_level.name})"

    # === Manager helpers (static/class methods) ===
    @staticmethod
    def current_for_employee(employee_id, on_date=None):
        """
        يعيد QuerySet للمهارات النشطة لموظف في تاريخ معيّن (اليوم افتراضيًا).
        - لغير الشهادات: سجل واحد نشط لكل Skill (تُغطيه قيود/signals).
        - للشهادات: يعيد السجلات التي يغطي نطاقها التاريخ.
        """
        on_date = on_date or timezone.now().date()
        qs = (HrEmployeeSkill.objects
              .filter(employee_id=employee_id)
              .filter(Q(valid_from__lte=on_date) & (Q(valid_to__isnull=True) | Q(valid_to__gte=on_date))))
        return qs
