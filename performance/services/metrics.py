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
