# performance/services.py
"""
خدمات الأداء:
- سجلّ Adapters لمصادر خارجية EXTERNAL_METRIC
- أدوات مساعدة للتجميع/القصّ/التحقق
"""

from typing import Optional, Tuple, Dict, Any, Callable
from django.apps import apps
from django.db import models
from django.db.models import QuerySet

AdapterFunc = Callable[..., Tuple[Optional[float], Dict[str, Any]]]
_REGISTRY: dict[str, AdapterFunc] = {}

# -----------------------------
# Adapters registry
# -----------------------------
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
    aggregation: 'sum' | 'avg' | 'latest'
    filter_json: يدعم placeholders {employee_id}/{company_id}/{date_start}/{date_end}
    """
    try:
        app_label, model_name = app_model.split(".", 1)
        Model = apps.get_model(app_label, model_name)
    except Exception:
        return None, {"error": "invalid_model"}

    if not Model:
        return None, {"error": "model_not_found"}

    flt = {k: _apply_placeholders(v, context) for k, v in (filter_json or {}).items()}

    # ✅ أمان الشركة: إن كان الموديل يحوي company_id ولم يضعه منادِي الخدمة، نحقنه من السياق
    try:
        has_company = any(f.name == "company" or f.attname == "company_id" for f in Model._meta.fields)
    except Exception:
        has_company = False
    if has_company and context.get("company_id") and ("company" not in flt and "company_id" not in flt):
        flt["company_id"] = context["company_id"]

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
        raw = float(values.order_by("-pk").first() or 0)
    else:
        return None, {"error": "invalid_aggregation"}

    return raw, {"count": len(vals), "agg": aggregation}

# تفعيل المحول الافتراضي
register_adapter("generic_model", generic_model_adapter)

# -----------------------------
# Helpers
# -----------------------------
def clamp_to_pct(v: Optional[float], lo: int, hi: int) -> int:
    if v is None:
        return 0
    return int(max(lo, min(hi, round(v))))

def objective_applies(evaluation, obj) -> bool:
    """
    هل ينطبق الهدف على موظّف/فترة التقييم؟
    - نفس الشركة
    - الفترة تتقاطع
    - الموظف ضمن المشاركين الماديين
    """
    if not obj or obj.company_id != evaluation.company_id:
        return False
    if obj.date_start > evaluation.date_end:
        return False
    if obj.date_end and obj.date_end < evaluation.date_start:
        return False
    from performance.models import ObjectiveParticipant
    return ObjectiveParticipant.objects.filter(objective=obj, employee=evaluation.employee).exists()

def avg_task_progress_for(evaluation, objective) -> int:
    """
    متوسط تقدّم المهام (0..100) لموظّف التقييم أو المهام غير المعينة، داخل الفترة.
    """
    from performance.models import Task
    qs = Task.objects.filter(objective=objective, company=evaluation.company).exclude(status__in=["cancelled"])
    qs = qs.filter(models.Q(assignee=evaluation.employee) | models.Q(assignee__isnull=True))
    qs = qs.filter(models.Q(due_date__isnull=True) | models.Q(due_date__range=(evaluation.date_start, evaluation.date_end)))
    n = qs.count()
    if not n:
        return 0
    return int(round(sum(t.percent_complete for t in qs) / n))


# ============================================================
# Workflow Services (NEW)
# ============================================================
def user_can_approve_step(user, evaluation) -> bool:
    """
    هل هذا المستخدم مخوّل باعتماد الخطوة الحالية؟
    (يدعم approver الفردي أو مجموعة role)
    """
    emp = getattr(user, "employee", None)
    if not emp:
        return False

    # إذا التقييم ليس في progress → لا يوجد موافقة
    if evaluation.state not in ("in_progress",):
        return False

    # جلب الخطوات
    steps = evaluation._get_steps()
    if not steps or evaluation.current_step <= 0:
        return False

    step = steps[evaluation.current_step - 1]

    # نوع الموافقة = مجموعة
    if step.approver_kind == step.ApproverKind.GROUP:
        # أي عضو من المجموعة يمكنه الموافقة
        if step.approver_group and user.groups.filter(id=step.approver_group_id).exists():
            return True
        return False

    # نوع الموافقة = موظف فردي
    if evaluation.current_approver_id == emp.id:
        return True

    return False


def submit_evaluation(evaluation, by_user):
    """
    تقديم التقييم لأول مرة.
    """
    emp = getattr(by_user, "employee", None)
    evaluation.submit(by=emp)
    return evaluation


def approve_step(evaluation, by_user) -> bool:
    """
    اعتماد خطوة في workflow.
    """
    emp = getattr(by_user, "employee", None)
    if not emp:
        return False

    if not user_can_approve_step(by_user, evaluation):
        return False

    evaluation.approve_step(emp)
    return True


def reject_step(evaluation, by_user) -> bool:
    """
    إعادة التقييم خطوة للخلف (Reject).
    """
    emp = getattr(by_user, "employee", None)
    if not emp:
        return False

    if not user_can_approve_step(by_user, evaluation):
        return False

    evaluation.reject_step(emp)
    return True
