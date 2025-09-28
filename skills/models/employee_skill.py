from django.db import models
from collections import defaultdict
from .individual_skill_mixin import HrIndividualSkillMixin
from hr.models import Employee  # من تطبيق HR

class HrEmployeeSkill(HrIndividualSkillMixin):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="employee_skills", db_index=True)

    class Meta:
        db_table = "hr_employee_skill"
        ordering = ["skill_type_id", "skill_level_id"]

    # linked field name لطبقة الميكسن
    def _linked_field_name(self):
        return "employee"

    # مطابق لفكرة get_current_skills_by_employee في Odoo
    @classmethod
    def get_current_skills_by_employee(cls):
        result = defaultdict(list)
        today = models.functions.Now()
        for es in cls.objects.select_related("employee", "skill", "skill_level", "skill_type"):
            active = (es.valid_to is None) or (es.valid_to >= es.valid_from)
            if es.is_certification and not active:
                # لو شهادة منتهية: اختر أحدث valid_to لكل زوج (employee, skill)
                result[es.employee_id].append(es)
                continue
            if active:
                result[es.employee_id].append(es)
        return result
