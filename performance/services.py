from typing import Optional
from django.db import models

# ------- metrics services -------

"""
External metrics & adapters registry.

Usage:
- Out of the box, `GenericModelAdapter` implements the template-based EXTERNAL_METRIC:
  (app_label.ModelName, field, aggregation, filter with placeholders).
- You can register custom adapters for special sources (e.g., attendance, call center).
"""

from typing import Optional, Tuple, Dict, Any, Callable, Type
from django.apps import apps
from django.db.models import QuerySet

AdapterFunc = Callable[..., Tuple[Optional[float], Dict[str, Any]]]

_REGISTRY: dict[str, AdapterFunc] = {}

def register_adapter(code: str, fn: AdapterFunc):
    _REGISTRY[code] = fn

def get_adapter(code: str) -> Optional[AdapterFunc]:
    return _REGISTRY.get(code)

# -----------------------------
# Default generic adapter
# -----------------------------

def _apply_placeholders(v: Any, ctx: Dict[str, Any]) -> Any:
    if isinstance(v, str):
        for k, val in ctx.items():
            v = v.replace(f"{{{k}}}", str(val))
    return v

def generic_model_adapter(
    *,
    app_model: str,
    field: str,
    aggregation: str,
    filter_json: Dict[str, Any],
    context: Dict[str, Any],
) -> Tuple[Optional[float], Dict[str, Any]]:
    """
    app_model: 'app_label.ModelName'
    field:     model field name
    aggregation: 'sum' | 'avg' | 'latest'
    filter_json: dict with optional placeholders {employee_id}, {company_id}, {date_start}, {date_end}
    """
    try:
        app_label, model_name = app_model.split(".", 1)
        Model = apps.get_model(app_label, model_name)
    except Exception:
        return None, {"error": "invalid_model"}

    if not Model:
        return None, {"error": "model_not_found"}

    flt = {k: _apply_placeholders(v, context) for k, v in (filter_json or {}).items()}
    qs: QuerySet = Model.objects.all()
    if flt:
        qs = qs.filter(**flt)

    values = qs.values_list(field, flat=True)
    vals = [float(x) for x in values if x is not None]
    if not vals:
        return None, {"count": 0}

    if aggregation == "sum":
        raw = sum(vals)
    elif aggregation == "avg":
        raw = sum(vals) / len(vals)
    elif aggregation == "latest":
        # naive 'latest' by PK
        raw = float(values.order_by("-pk").first() or 0)
    else:
        return None, {"error": "invalid_aggregation"}

    return raw, {"count": len(vals), "agg": aggregation}

# Register default adapter under a stable code
register_adapter("generic_model", generic_model_adapter)


# ------- scoring services -------

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
