from django.db import models
from collections import defaultdict
from .mixins import TimeStamped
from .individual_skill_mixin import HrIndividualSkillMixin
from hr.models import Employee  # your HR app


class HrEmployeeSkill(HrIndividualSkillMixin):
    """
    Employee-linked skill record. Mirrors Odoo's hr.employee.skill. :contentReference[oaicite:25]{index=25}
    """
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="skills", db_index=True)

    class Meta:
        db_table = "hr_employee_skill"
        ordering = ["skill_type_id", "skill_level_id"]

    def _linked_field_name(self) -> str:
        return "employee"

    @classmethod
    def get_current_skills_by_employee(cls):
        """
        Matches Odoo helper: returns a dict[employee_id] -> queryset of current/most-recent skills.
        - For certifications: if none active, keep the most recent expired interval. :contentReference[oaicite:26]{index=26}
        """
        result = defaultdict(lambda: cls.objects.none())
        all_skills = cls.objects.select_related("skill", "skill_type", "skill_level", "employee")
        buckets = defaultdict(list)
        for s in all_skills:
            buckets[(s.employee_id, s.skill_id_id)].append(s)

        for (emp_id, _skill_id), items in buckets.items():
            active = [x for x in items if (not x.valid_to) or (x.valid_to >= models.functions.Now())]
            if active:
                # regular skills → single active; certifications → possibly multiple windows
                result[emp_id] = cls.objects.filter(pk__in=[a.pk for a in active])
            else:
                # for certifications keep the most recent expired window
                certs = [x for x in items if x.is_certification and x.valid_to]
                if certs:
                    latest_to = max(c.valid_to for c in certs)
                    keep = [c.pk for c in certs if c.valid_to == latest_to]
                    result[emp_id] = cls.objects.filter(pk__in=keep)
                else:
                    result[emp_id] = cls.objects.none()
        return result
