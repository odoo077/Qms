# performance/services/scoring.py
"""
Scoring helpers used by Evaluation. Kept small & testable.
All model imports are inside functions to avoid circular imports.
"""
from typing import Optional
from django.db import models


def clamp_to_pct(v: Optional[float], lo: int, hi: int) -> int:
    if v is None:
        return 0
    return int(max(lo, min(hi, round(v))))


def objective_applies(evaluation, obj) -> bool:
    """
    Check if an Objective applies to the evaluation's employee and period.
    Local import avoids circular imports.
    """
    if not obj or obj.company_id != evaluation.company_id:
        return False
    if obj.date_start > evaluation.date_end:
        return False
    if obj.date_end and obj.date_end < evaluation.date_start:
        return False

    # Local import to avoid cycle
    from performance.models import ObjectiveParticipant
    return ObjectiveParticipant.objects.filter(objective=obj, employee=evaluation.employee).exists()


def avg_task_progress_for(evaluation, objective) -> int:
    """
    Average of Task.percent_complete for the evaluation's employee
    (or unassigned tasks) under the objective and within the period.
    """
    # Local import to avoid cycle
    from performance.models import Task

    qs = Task.objects.filter(objective=objective, company=evaluation.company).exclude(status__in=["cancelled"])
    qs = qs.filter(models.Q(assignee=evaluation.employee) | models.Q(assignee__isnull=True))
    qs = qs.filter(models.Q(due_date__isnull=True) |
                   models.Q(due_date__range=(evaluation.date_start, evaluation.date_end)))
    n = qs.count()
    if not n:
        return 0
    return int(round(sum(t.percent_complete for t in qs) / n))
