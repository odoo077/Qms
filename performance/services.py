# performance/services.py
# ======================================================================
# Unified Services + Adapters + Engines (COMPLETE)
# ======================================================================

from typing import Optional, Tuple, Dict, Any, Callable
from django.apps import apps
from django.db import transaction, models
from django.utils import timezone
from django.core.exceptions import ValidationError

from performance.models import (
    Task,
    ObjectiveParticipant,
    TaskRecurringDefinition,
)

# ======================================================================
# ADAPTERS REGISTRY  (External Metric Support)
# ======================================================================

AdapterFunc = Callable[..., Tuple[Optional[float], Dict[str, Any]]]
_REGISTRY: dict[str, AdapterFunc] = {}

def register_adapter(code: str, fn: AdapterFunc):
    _REGISTRY[code] = fn

def get_adapter(code: str) -> Optional[AdapterFunc]:
    return _REGISTRY.get(code)

# ======================================================================
# Generic External Model Adapter
# ======================================================================

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
    Generic adapter used for external metrics.
    """
    try:
        app_label, model_name = app_model.split(".", 1)
        Model = apps.get_model(app_label, model_name)
    except Exception:
        return None, {"error": "invalid_model"}

    if not Model:
        return None, {"error": "model_not_found"}

    flt = {k: _apply_placeholders(v, context) for k, v in (filter_json or {}).items()}

    # Auto-inject company_id if supported by model
    try:
        has_company = any(f.name == "company" or f.attname == "company_id" for f in Model._meta.fields)
    except Exception:
        has_company = False

    if has_company and context.get("company_id") and "company_id" not in flt:
        flt["company_id"] = context["company_id"]

    qs = Model.objects.all()
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


# Register the generic adapter
register_adapter("generic_model", generic_model_adapter)


# ======================================================================
# COMMON HELPERS
# ======================================================================

def clamp_to_pct(v: Optional[float], lo: int, hi: int) -> int:
    """Clamp a number into percentage boundaries."""
    if v is None:
        return 0
    return int(max(lo, min(hi, round(v))))


def objective_applies(evaluation, obj) -> bool:
    """
    Does an objective apply to this evaluation?
    - same company
    - intersecting date periods
    - employee is a participant
    """
    if not obj or obj.company_id != evaluation.company_id:
        return False
    if obj.date_start > evaluation.date_end:
        return False
    if obj.date_end and obj.date_end < evaluation.date_start:
        return False

    return ObjectiveParticipant.objects.filter(
        objective=obj,
        employee=evaluation.employee
    ).exists()


def avg_task_progress_for(evaluation, objective) -> int:
    """
    Average progress of tasks for employee within date range.
    """
    qs = Task.objects.filter(
        objective=objective,
        company=evaluation.company
    ).exclude(status__in=["cancelled"])

    qs = qs.filter(
        models.Q(assignee=evaluation.employee) |
        models.Q(assignee__isnull=True)
    )

    qs = qs.filter(
        models.Q(due_date__isnull=True) |
        models.Q(due_date__range=(evaluation.date_start, evaluation.date_end))
    )

    n = qs.count()
    if not n:
        return 0

    return int(round(sum(t.percent_complete for t in qs) / n))


# ======================================================================
# TASK SLA ENGINE
# ======================================================================

class TaskSLAEngine:
    @staticmethod
    def compute_timeliness(task: Task):
        if not task.sla_policy:
            return 100

        policy = task.sla_policy

        if not task.due_date:
            return policy.on_time_pct

        completed_at = task.completed_at or timezone.now()

        if task.blocked_external and policy.allow_blocked_external_no_penalty:
            return policy.on_time_pct

        delta = (completed_at.date() - task.due_date).days

        if delta <= 0:
            return policy.on_time_pct

        if 0 < delta <= 3:
            return policy.mild_delay_pct

        return policy.severe_delay_pct


# ======================================================================
# TASK EFFICIENCY ENGINE
# ======================================================================

class TaskEfficiencyEngine:
    @staticmethod
    def compute_efficiency(task: Task):
        est = task.estimated_minutes
        act = task.actual_minutes

        if est <= 0:
            return 100

        ratio = act / est

        if ratio <= 1:
            return 100

        if 1 < ratio <= 1.3:
            return 80

        return 50


# ======================================================================
# SUBTASK ENGINE
# ======================================================================

class TaskSubtaskEngine:
    @staticmethod
    def compute_from_subtasks(task: Task):
        subs = task.subtasks.filter(active=True)
        if not subs.exists():
            return None

        total = sum(t.percent_complete for t in subs)
        return int(round(total / subs.count()))


# ======================================================================
# DEPENDENCY ENGINE
# ======================================================================

class TaskDependencyEngine:
    @staticmethod
    def validate_dependencies(task: Task):
        needed = task.depends_on.filter(active=True).all()

        for parent in needed:
            if not parent.status or not parent.status.is_closed:
                raise ValidationError(
                    f"Cannot start or complete this task because dependency '{parent.title}' is not finished."
                )


# ======================================================================
# PROGRESS ENGINE
# ======================================================================

class TaskProgressEngine:
    @staticmethod
    def compute_progress(task: Task) -> int:
        policy = task.progress_policy

        # -----------------------------------------
        # 1) إذا كانت السياسة تعتمد على Subtasks
        #    نأخذ التقدم من الـ Subtasks فقط
        # -----------------------------------------
        if policy and policy.use_subtasks:
            sub_pct = TaskSubtaskEngine.compute_from_subtasks(task)
            if sub_pct is not None:
                return max(0, min(int(sub_pct), 100))

        # -----------------------------------------
        # 2) إذا كانت السياسة تعتمد على time ratio
        #    progress = actual / estimated
        # -----------------------------------------
        if policy and policy.use_time_ratio and task.estimated_minutes > 0:
            ratio = task.actual_minutes / task.estimated_minutes
            ratio = max(0, min(ratio, 1))  # حصر النسبة بين 0 و 1
            return int(round(ratio * 100))

        # -----------------------------------------
        # 3) إذا كانت السياسة تعتمد على status mapping
        # -----------------------------------------
        if policy and policy.use_status_mapping:
            st = task.status.code if task.status else None

            # حالات البداية / عدم التعيين
            if st in (None, "", "todo"):
                return 0

            # in_progress لا تعطي نسبة تلقائية
            # نبقي القيمة كما هي (عادةً تبدأ من 0)
            if st == "in_progress":
                return max(0, min(task.percent_complete, 100))

            # أي حالة مغلقة تعطي 100%
            if task.status and task.status.is_closed:
                return 100

            # أي حالات أخرى نعيد فيها القيمة الحالية بعد حصرها
            return max(0, min(task.percent_complete, 100))

        # -----------------------------------------
        # 4) في حال عدم وجود سياسة أو أي شرط آخر
        #    نستخدم القيمة الحالية بعد حصرها
        # -----------------------------------------
        return max(0, min(task.percent_complete, 100))



# ======================================================================
# QUALITY ENGINE
# ======================================================================

class TaskQualityEngine:
    @staticmethod
    def compute_quality(task: Task):
        if task.quality_score_pct and task.quality_score_pct > 0:
            return task.quality_score_pct
        return 100


# ======================================================================
# MAIN TASK ENGINE
# ======================================================================

class TaskPolicyEngine:
    @staticmethod
    def apply(task: Task):
        if task.status and task.status.code in ("in_progress", "done"):
            TaskDependencyEngine.validate_dependencies(task)

        task.percent_complete = TaskProgressEngine.compute_progress(task)
        task.timeliness_pct = TaskSLAEngine.compute_timeliness(task)
        task.efficiency_pct = TaskEfficiencyEngine.compute_efficiency(task)
        task.quality_pct = TaskQualityEngine.compute_quality(task)

        return task


# ======================================================================
# OBJECTIVE SCORE ENGINE
# ======================================================================

class ObjectiveScoreEngine:
    @staticmethod
    def aggregate_for_employee(objective, employee):
        tasks = objective.tasks.filter(active=True, assignee=employee)

        if not tasks.exists():
            return {"timeliness": 100, "efficiency": 100, "quality": 100}

        tim = int(sum(t.timeliness_pct for t in tasks) / tasks.count())
        eff = int(sum(t.efficiency_pct for t in tasks) / tasks.count())
        qua = int(sum(t.quality_pct for t in tasks) / tasks.count())

        return {"timeliness": tim, "efficiency": eff, "quality": qua}


# ======================================================================
# RECURRING TASK SERVICE
# ======================================================================

class RecurringTaskService:
    @staticmethod
    @transaction.atomic
    def generate_tasks(definition: TaskRecurringDefinition, period_label: str):
        objective = definition.objective

        participants = objective.participants.values_list("employee_id", flat=True)
        excluded = definition.excluded_employees.values_list("id", flat=True)

        final_ids = [eid for eid in participants if eid not in excluded]

        created = []

        for emp_id in final_ids:
            task = Task.objects.create(
                company=objective.company,
                objective=objective,
                task_type=definition.task_type,
                task_category=definition.task_category,
                assignee_id=emp_id,
                title=f"{definition.name} – {period_label}",
                description=definition.description,
                estimated_minutes=definition.target_count,
                due_date=timezone.now().date(),
                status=None,
            )
            created.append(task)

        return created
