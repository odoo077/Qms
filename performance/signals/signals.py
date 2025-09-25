from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from performance.models import (
    Objective, KPI, Task,
    ObjectiveDepartmentAssignment, ObjectiveEmployeeAssignment
)

# -----------------------------
# Participants: rebuild when assignments change
# -----------------------------


@receiver(post_save, sender=ObjectiveDepartmentAssignment)
@receiver(post_delete, sender=ObjectiveDepartmentAssignment)
def rebuild_participants_on_dept_assignment_change(sender, instance, **kwargs):
    obj = instance.objective
    # Safe guard: only for persisted objectives
    if obj and obj.pk:
        obj._rebuild_participants()


@receiver(post_save, sender=ObjectiveEmployeeAssignment)
@receiver(post_delete, sender=ObjectiveEmployeeAssignment)
def rebuild_participants_on_emp_assignment_change(sender, instance, **kwargs):
    obj = instance.objective
    if obj and obj.pk:
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
    if instance.objective_id:
        _recompute_objective(instance.objective)


@receiver(post_save, sender=Task)
@receiver(post_delete, sender=Task)
def recompute_objective_on_task_change(sender, instance, **kwargs):
    if instance.objective_id:
        _recompute_objective(instance.objective)
