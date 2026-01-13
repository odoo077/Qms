# performance/signals.py
"""
Signals:
- إعادة بناء المشاركين عند تغيّر تعيينات الأقسام/الموظفين.
- إعادة تجميع الهدف عند تغيّر KPI/Task.
- منح صلاحيات الكائن للمنشئ (Guardian).
- إنشاء مجموعات وصلاحيات افتراضية بعد الترحيل.
"""

from typing import Optional

from django.db.models.signals import post_save, post_delete, post_migrate
from django.dispatch import receiver
from performance.models import (
    Objective, KPI, Task,
    ObjectiveDepartmentAssignment, ObjectiveEmployeeAssignment, ObjectiveParticipant,
    EvaluationTemplate, EvaluationParameter, Evaluation, EvaluationParameterResult,
)
from . import models as m


# -----------------------------
# Participants: rebuild on assignments change
# -----------------------------
def _get_objective_safe(obj_id) -> Optional[Objective]:
    if not obj_id:
        return None
    try:
        return Objective.objects.only("id").get(pk=obj_id)
    except Objective.DoesNotExist:
        return None


@receiver(post_save, sender=ObjectiveDepartmentAssignment)
@receiver(post_delete, sender=ObjectiveDepartmentAssignment)
def rebuild_participants_on_dept_assignment_change(sender, instance, **kwargs):
    obj = _get_objective_safe(getattr(instance, "objective_id", None))
    if obj:
        obj._rebuild_participants()


@receiver(post_save, sender=ObjectiveEmployeeAssignment)
@receiver(post_delete, sender=ObjectiveEmployeeAssignment)
def rebuild_participants_on_emp_assignment_change(sender, instance, **kwargs):
    obj = _get_objective_safe(getattr(instance, "objective_id", None))
    if obj:
        obj._rebuild_participants()


# -----------------------------
# Objective aggregations bubble-up
# -----------------------------
def _recompute_objective(obj: Objective):
    obj.recompute_progress_and_score()
    obj.save(update_fields=["progress_pct", "score_pct"])


# -----------------------------
# Object-level permissions (creator ownership)
# -----------------------------
# تم حذف جميع إشارات ومنطق ACL (grant_access / apply_default_acl)
# دون أي تغيير في باقي منطق الملف.


