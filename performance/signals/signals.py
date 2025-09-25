from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from performance.models import (
    Objective, KPI, Task,
    ObjectiveDepartmentAssignment, ObjectiveEmployeeAssignment
)

# -----------------------------
# Participants: rebuild when assignments change
# -----------------------------

from typing import Optional

def _get_objective_safe(obj_id) -> Optional[Objective]:
    if not obj_id:
        return None
    try:
        return Objective.objects.only("id").get(pk=obj_id)
    except Objective.DoesNotExist:
        return None

# -----------------------------
# Participants: rebuild when assignments change
# -----------------------------


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
# Objective aggregations: bubble up on KPI/Task changes
# -----------------------------

def _recompute_objective(obj: Objective):
    # Recompute progress & score and persist (only fields)
    obj.recompute_progress_and_score()
    obj.save(update_fields=["progress_pct", "score_pct"])


@receiver(post_save, sender=KPI)
@receiver(post_delete, sender=KPI)
def recompute_objective_on_kpi_change(sender, instance, **kwargs):
    obj = _get_objective_safe(getattr(instance, "objective_id", None))
    if obj:
        _recompute_objective(obj)


@receiver(post_save, sender=Task)
@receiver(post_delete, sender=Task)
def recompute_objective_on_task_change(sender, instance, **kwargs):
    obj = _get_objective_safe(getattr(instance, "objective_id", None))
    if obj:
        _recompute_objective(obj)

# Note: We fetch Objective by id inside signals instead of touching instance.objective directly
# because post_delete handlers may run after the related Objective has been removed (cascade),
# and dereferencing `instance.objective` could raise DoesNotExist. Using the id avoids that race.
