# skills/services.py
# ============================================================
# Services for Skills app (Odoo-like)
# - طبقة خدمات للتعامل مع SkillType/SkillLevel/Skill/EmployeeSkill/ResumeLine
# - تعليقات عربية، وكود إنجليزي
# ============================================================

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable, List, Optional, Sequence, Tuple
from django.apps import apps
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import transaction
from django.db.models import Q
from datetime import timedelta
# ------------------------------------------------------------
# Dynamic model getters (تجنب دورات الاستيراد المباشر)
# ------------------------------------------------------------
SkillType = apps.get_model("skills", "SkillType")
SkillLevel = apps.get_model("skills", "SkillLevel")
Skill = apps.get_model("skills", "Skill")
EmployeeSkill = apps.get_model("skills", "EmployeeSkill")
ResumeLineType = apps.get_model("skills", "ResumeLineType")
ResumeLine = apps.get_model("skills", "ResumeLine")

# ============================================================
# Data Contracts (مدخلات/مخرجات واضحة)
# ============================================================

@dataclass(frozen=True)
class EmployeeSkillInput:
    """حزمة بيانات قياسية لإنشاء/تحديث مهارة موظف."""
    employee_id: int
    skill_type_id: int
    skill_id: int
    skill_level_id: int
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    note: str = ""
    created_by_id: Optional[int] = None
    updated_by_id: Optional[int] = None


@dataclass(frozen=True)
class ResumeLineInput:
    """حزمة بيانات قياسية لإنشاء/تحديث سطر السيرة."""
    employee_id: int
    line_type_id: int
    name: str
    description: str = ""
    date_start: Optional[date] = None
    date_end: Optional[date] = None
    external_url: str = ""
    created_by_id: Optional[int] = None
    updated_by_id: Optional[int] = None


# ============================================================
# Helpers (مساعدات منطقية مشتركة)
# ============================================================

def _normalize_period(dt_from: Optional[date], dt_to: Optional[date]) -> Tuple[Optional[date], Optional[date]]:
    """
    توحيد التواريخ والتحقق الأساسي: إن كان كلاهما محددًا يجب أن dt_to >= dt_from.
    (التحقق الأعمق يتم أيضًا داخل model.clean())
    """
    if dt_from and dt_to and dt_to < dt_from:
        raise ValidationError({"valid_to": "Date to must be after or equal to Date from."})
    return dt_from, dt_to


def _normalize_resume_period(
    dt_from: Optional[date],
    dt_to: Optional[date],
) -> Tuple[Optional[date], Optional[date]]:
    if dt_from and dt_to and dt_to < dt_from:
        raise ValidationError({"date_end": "Date to must be after or equal to Date from."})
    return dt_from, dt_to


def _ensure_type_coherence(skill_type_id: int, skill_id: int, skill_level_id: int) -> None:
    """
    التحقق من اتساق النوع:
    - skill.skill_type == skill_type
    - level.skill_type == skill_type
    (نفس منطق CheckConstraint داخل الموديل، مع رسالة أوضح قبل الحفظ)
    """
    try:
        s = Skill.objects.only("skill_type_id").get(pk=skill_id)
        lvl = SkillLevel.objects.only("skill_type_id").get(pk=skill_level_id)
    except ObjectDoesNotExist:
        # سيظهر خطأ أوضح لاحقًا عند clean() إذا لم توجد السجلات؛ لا نُثقِل هنا.
        raise ValidationError("Invalid skill or skill level.")

    if s.skill_type_id != skill_type_id:
        raise ValidationError({"skill": "Skill must belong to the selected skill type."})
    if lvl.skill_type_id != skill_type_id:
        raise ValidationError({"skill_level": "Level must belong to the selected skill type."})


def _get_employee_skill_q(employee_id: int, skill_id: int):
    """QueryHelper: سطر المهارة الفريد وفق قيد Unique(employee, skill)."""
    return EmployeeSkill.objects.filter(employee_id=employee_id, skill_id=skill_id)


# ============================================================
# EmployeeSkill Services
# ============================================================

@transaction.atomic
def add_employee_skill(data: EmployeeSkillInput) -> EmployeeSkill:
    """
    إنشاء سجل مهارة للموظف (Strict Create).
    - يفشل إذا وُجد سجل بنفس (employee, skill) طبقًا لقيد Unique.
    - يمرّ عبر full_clean() لاحترام جميع قيود models.py.
    """
    # 1) تحقق التواريخ/الاتساق
    valid_from, valid_to = _normalize_period(data.valid_from, data.valid_to)
    _ensure_type_coherence(data.skill_type_id, data.skill_id, data.skill_level_id)

    # 2) تحضير السجل
    obj = EmployeeSkill(
        employee_id=data.employee_id,
        skill_type_id=data.skill_type_id,
        skill_id=data.skill_id,
        skill_level_id=data.skill_level_id,
        valid_from=valid_from,
        valid_to=valid_to,
        note=data.note or "",
        created_by_id=data.created_by_id,
        updated_by_id=data.updated_by_id,
    )

    # 3) فحوصات الموديل ثم الحفظ
    obj.full_clean()   # سيتحقق من unique/constraints + ملء company عبر clean/save
    obj.save()
    return obj


@transaction.atomic
def ensure_employee_skill(data: EmployeeSkillInput) -> EmployeeSkill:
    """
    Upsert: إن وجد (employee, skill) نُحدّثه، وإلا ننشئ سجلًا جديدًا.
    - يحترم قيد Unique في الموديل.
    - مفيد عندما تريد تثبيت آخر مستوى/ملاحظات لنفس المهارة.
    """
    valid_from, valid_to = _normalize_period(data.valid_from, data.valid_to)
    _ensure_type_coherence(data.skill_type_id, data.skill_id, data.skill_level_id)

    qs = _get_employee_skill_q(data.employee_id, data.skill_id)
    if qs.exists():
        obj = qs.select_for_update().get()
        # تحديث الحقول
        obj.skill_type_id = data.skill_type_id
        obj.skill_level_id = data.skill_level_id
        obj.valid_from = valid_from
        obj.valid_to = valid_to
        obj.note = data.note or obj.note
        if data.updated_by_id:
            obj.updated_by_id = data.updated_by_id
        obj.full_clean()
        obj.save()
        return obj

    # غير موجود → إنشاء
    return add_employee_skill(data)


@transaction.atomic
def update_employee_skill(
    employeeskill_id: int,
    *,
    skill_type_id: Optional[int] = None,
    skill_id: Optional[int] = None,
    skill_level_id: Optional[int] = None,
    valid_from: Optional[date] = None,
    valid_to: Optional[date] = None,
    note: Optional[str] = None,
    updated_by_id: Optional[int] = None,
) -> EmployeeSkill:
    """
    تحديث سجّل مهارة موظف.
    - يراعي قيود الاتساق وقيد Unique.
    - إن تغيّر employee/skill إلى تركيبة موجودة ستفشل full_clean() (كما ينبغي).
    """
    obj = EmployeeSkill.objects.select_for_update().get(pk=employeeskill_id)

    # مسك قيم جديدة
    if skill_type_id is not None:
        obj.skill_type_id = skill_type_id
    if skill_id is not None:
        obj.skill_id = skill_id
    if skill_level_id is not None:
        obj.skill_level_id = skill_level_id
    if valid_from is not None or valid_to is not None:
        vf = valid_from if valid_from is not None else obj.valid_from
        vt = valid_to if valid_to is not None else obj.valid_to
        vf, vt = _normalize_period(vf, vt)
        obj.valid_from, obj.valid_to = vf, vt
    if note is not None:
        obj.note = note
    if updated_by_id:
        obj.updated_by_id = updated_by_id

    # تحقّق اتساق النوع (إن تغيّر شيء)
    _ensure_type_coherence(obj.skill_type_id, obj.skill_id, obj.skill_level_id)

    obj.full_clean()
    obj.save()
    return obj


@transaction.atomic
def delete_employee_skill(employeeskill_id: int) -> None:
    """
    حذف سجل مهارة موظف.
    """
    EmployeeSkill.objects.filter(pk=employeeskill_id).delete()


@transaction.atomic
def bulk_ensure_employee_skills(
    items: Sequence[EmployeeSkillInput],
) -> List[EmployeeSkill]:
    """
    معالجة مجموعة مهارات (Upsert لكل عنصر) بذرة واحدة.
    - تُعيد قائمة السجلات بعد التحديث/الإنشاء.
    - أي فشل ValidationError يوقف العملية كلها (atomic).
    """
    out: List[EmployeeSkill] = []
    for it in items:
        out.append(ensure_employee_skill(it))
    return out


# ============================================================
# ResumeLine Services
# ============================================================

@transaction.atomic
def add_resume_line(data: ResumeLineInput) -> ResumeLine:
    """
    إنشاء سطر سيرة ذاتية لموظف.
    - يمر عبر full_clean() لاحترام قيود التاريخ وملء company من employee.
    """
    date_start, date_end = _normalize_resume_period(data.date_start, data.date_end)

    obj = ResumeLine(
        employee_id=data.employee_id,
        line_type_id=data.line_type_id,
        name=data.name,
        description=data.description or "",
        date_start=data.date_start,
        date_end=data.date_end,
        external_url=data.external_url or "",
        created_by_id=data.created_by_id,
        updated_by_id=data.updated_by_id,
    )
    obj.full_clean()
    obj.save()
    return obj


@transaction.atomic
def update_resume_line(
    resumeline_id: int,
    *,
    line_type_id: Optional[int] = None,
    name: Optional[str] = None,
    description: Optional[str] = None,
    date_start: Optional[date] = None,
    date_end: Optional[date] = None,
    external_url: Optional[str] = None,
    updated_by_id: Optional[int] = None,
) -> ResumeLine:
    """
    تحديث سطر سيرة.
    - يتأكد من منطق التاريخ ويستدعي full_clean() قبل الحفظ.
    """
    obj = ResumeLine.objects.select_for_update().get(pk=resumeline_id)
    if line_type_id is not None:
        obj.line_type_id = line_type_id
    if name is not None:
        obj.name = name
    if description is not None:
        obj.description = description
    if (date_start is not None) or (date_end is not None):
        ds = date_start if date_start is not None else obj.date_start
        de = date_end if date_end is not None else obj.date_end
        if ds and de and de < ds:
            raise ValidationError({"date_end": "Date to must be after or equal to Date from."})
        obj.date_start, obj.date_end = ds, de
    if external_url is not None:
        obj.external_url = external_url
    if updated_by_id:
        obj.updated_by_id = updated_by_id

    obj.full_clean()
    obj.save()
    return obj


@transaction.atomic
def delete_resume_line(resumeline_id: int) -> None:
    """حذف سطر سيرة."""
    ResumeLine.objects.filter(pk=resumeline_id).delete()


# ============================================================
# Query Utilities (مُساعدة للاستعلامات الشائعة)
# ============================================================

def list_employee_skills_for_employee(
    employee_id: int,
    *,
    only_active: bool = True,
    order_by: Iterable[str] = ("skill_type__sequence", "skill__name"),
):
    """
    قائمة مهارات موظف واحد، مع ترتيب منطقي.
    """
    qs = EmployeeSkill.objects.filter(employee_id=employee_id)
    if only_active and hasattr(EmployeeSkill, "active"):
        qs = qs.filter(active=True)
    return qs.order_by(*order_by)


def list_employee_skills_for_company(
    company_id: int,
    *,
    only_active: bool = True,
    search: Optional[str] = None,
):
    """
    """
    qs = EmployeeSkill.objects.filter(company_id=company_id)
    if only_active and hasattr(EmployeeSkill, "active"):
        qs = qs.filter(active=True)
    if search:
        qs = qs.filter(
            Q(employee__name__icontains=search)
            | Q(skill__name__icontains=search)
            | Q(skill_type__name__icontains=search)
        )
    return qs.order_by("employee__name", "skill_type__sequence", "skill__name")


def list_resume_lines_for_employee(
    employee_id: int,
    *,
    only_active: bool = True,
    order_by: Iterable[str] = ("line_type__sequence", "-date_start", "name"),
):
    """
    قائمة أسطر السيرة لموظف.
    """
    qs = ResumeLine.objects.filter(employee_id=employee_id)
    if only_active and hasattr(ResumeLine, "active"):
        qs = qs.filter(active=True)
    return qs.order_by(*order_by)


# ============================================================
# Convenience Shortcuts (اختصارات جاهزة)
# ============================================================

@transaction.atomic
def set_employee_skill_level(
    *,
    employee_id: int,
    skill_id: int,
    skill_level_id: int,
    skill_type_id: Optional[int] = None,
    note: str = "",
    created_by_id: Optional[int] = None,
    updated_by_id: Optional[int] = None,
) -> EmployeeSkill:
    """
    اختصار عملي: اضبط مستوى مهارة معينة لموظف (Upsert).
    - إن لم يُمرر skill_type_id نستنتجه من Skill تلقائيًا.
    """
    if skill_type_id is None:
        skill_type_id = Skill.objects.only("skill_type_id").get(pk=skill_id).skill_type_id

    payload = EmployeeSkillInput(
        employee_id=employee_id,
        skill_type_id=skill_type_id,
        skill_id=skill_id,
        skill_level_id=skill_level_id,
        note=note,
        created_by_id=created_by_id,
        updated_by_id=updated_by_id,
    )
    return ensure_employee_skill(payload)


@transaction.atomic
def add_simple_resume_line(
    *,
    employee_id: int,
    line_type_id: int,
    title: str,
    description: str = "",
    created_by_id: Optional[int] = None,
    updated_by_id: Optional[int] = None,
) -> ResumeLine:
    """
    اختصار عملي: أضِف سطر سيرة بسيط بعنوان ووصف فقط.
    """
    payload = ResumeLineInput(
        employee_id=employee_id,
        line_type_id=line_type_id,
        name=title,
        description=description,
        created_by_id=created_by_id,
        updated_by_id=updated_by_id,
    )
    return add_resume_line(payload)




#------------------------

from dataclasses import dataclass
from typing import List, Optional, Dict

from hr.models import Employee, CareerPolicy, EmployeeReadinessSnapshot
from skills.models import EmployeeSkill, JobSkill


# ============================================================
# Skill Gap Analysis (JobSkill vs EmployeeSkill)
# ============================================================

@dataclass(frozen=True)
class SkillGapRow:
    required_skill: object           # Skill instance
    required_level: object           # SkillLevel instance (min_level)
    employee_level: Optional[object] # SkillLevel instance
    status: str                      # "ok" | "gap" | "missing"
    delta_progress: Optional[int]    # required - employee (only when gap)


def compute_employee_job_gap(employee: Employee) -> List[SkillGapRow]:
    """
    Odoo-like Skill Gap:
    - Driven by JobSkill (requirements)
    - Matches EmployeeSkill by skill_id
    - Compares using SkillLevel.level_progress (0..100)
    - ACTIVE only
    """
    if not employee or not employee.job_id:
        return []

    req_qs = (
        JobSkill.objects
        .filter(job_id=employee.job_id, active=True)
        .select_related(
            "skill", "skill__skill_type",
            "min_level", "min_level__skill_type",
        )
        .order_by("skill__skill_type__sequence", "skill__name")
    )

    emp_qs = (
        EmployeeSkill.objects
        .filter(employee_id=employee.id, active=True)
        .select_related("skill", "skill__skill_type", "skill_level", "skill_type")
    )

    # Map: skill_id -> best employee skill by level_progress
    emp_best: Dict[int, EmployeeSkill] = {}
    for es in emp_qs:
        if not es.skill_id or not es.skill_level_id:
            continue
        cur = emp_best.get(es.skill_id)
        if cur is None or es.skill_level.level_progress > cur.skill_level.level_progress:
            emp_best[es.skill_id] = es

    rows: List[SkillGapRow] = []

    for js in req_qs:
        es = emp_best.get(js.skill_id)

        if es is None:
            rows.append(
                SkillGapRow(
                    required_skill=js.skill,
                    required_level=js.min_level,
                    employee_level=None,
                    status="missing",
                    delta_progress=None,
                )
            )
            continue

        emp_p = es.skill_level.level_progress
        req_p = js.min_level.level_progress

        if emp_p >= req_p:
            rows.append(
                SkillGapRow(
                    required_skill=js.skill,
                    required_level=js.min_level,
                    employee_level=es.skill_level,
                    status="ok",
                    delta_progress=0,
                )
            )
        else:
            rows.append(
                SkillGapRow(
                    required_skill=js.skill,
                    required_level=js.min_level,
                    employee_level=es.skill_level,
                    status="gap",
                    delta_progress=req_p - emp_p,
                )
            )

    return rows

def compute_employee_job_gap_for_job(employee: Employee, job) -> List[SkillGapRow]:
    if not employee or not job:
        return []

    req_qs = (
        JobSkill.objects
        .filter(job_id=job.id, active=True)
        .select_related(
            "skill", "skill__skill_type",
            "min_level", "min_level__skill_type",
        )
        .order_by("skill__skill_type__sequence", "skill__name")
    )

    emp_qs = (
        EmployeeSkill.objects
        .filter(employee_id=employee.id, active=True)
        .select_related("skill", "skill__skill_type", "skill_level", "skill_type")
    )

    emp_best = {}
    for es in emp_qs:
        if not es.skill_id or not es.skill_level_id:
            continue
        cur = emp_best.get(es.skill_id)
        if cur is None or es.skill_level.level_progress > cur.skill_level.level_progress:
            emp_best[es.skill_id] = es

    rows = []

    for js in req_qs:
        es = emp_best.get(js.skill_id)

        if es is None:
            rows.append(
                SkillGapRow(
                    required_skill=js.skill,
                    required_level=js.min_level,
                    employee_level=None,
                    status="missing",
                    delta_progress=None,
                )
            )
            continue

        emp_p = es.skill_level.level_progress
        req_p = js.min_level.level_progress

        if emp_p >= req_p:
            rows.append(
                SkillGapRow(
                    required_skill=js.skill,
                    required_level=js.min_level,
                    employee_level=es.skill_level,
                    status="ok",
                    delta_progress=0,
                )
            )
        else:
            rows.append(
                SkillGapRow(
                    required_skill=js.skill,
                    required_level=js.min_level,
                    employee_level=es.skill_level,
                    status="gap",
                    delta_progress=req_p - emp_p,
                )
            )

    return rows

# ============================================================
# Job Fit Score (Enterprise Best Practice)
# ============================================================

@dataclass(frozen=True)
class JobFitScore:
    score: int              # 0..100
    label: str              # Text for management
    ok: int
    gap: int
    missing: int



def resolve_career_policy_for_employee(employee):
    """
    Resolve active CareerPolicy for employee (Company-level).
    Best Practice:
    - One active policy per company
    - Fallback-safe
    """
    if not employee or not employee.company_id:
        return None

    return (
        CareerPolicy.objects
        .filter(
            company_id=employee.company_id,
            active=True,
        )
        .order_by("-created_at")
        .first()
    )

def compute_employee_job_fit_score(employee: Employee) -> JobFitScore:
    """
    Job Fit Score (Policy-driven, Enterprise-grade)

    - Uses CareerPolicy (Company-level)
    - No magic numbers
    - Fully auditable & configurable
    """

    rows = compute_employee_job_gap(employee)

    # Resolve policy
    policy = resolve_career_policy_for_employee(employee)

    # Fallback safety (should not happen in production)
    if not policy:
        return JobFitScore(
            score=0,
            label="No Career Policy",
            ok=0,
            gap=0,
            missing=0,
        )

    if not rows:
        return JobFitScore(
            score=100,
            label="No Job Requirements",
            ok=0,
            gap=0,
            missing=0,
        )

    total = len(rows)

    ok = sum(1 for r in rows if r.status == "ok")
    gap = sum(1 for r in rows if r.status == "gap")
    missing = sum(1 for r in rows if r.status == "missing")

    weighted_score = (
        (ok * policy.ok_weight) +
        (gap * policy.gap_weight) +
        (missing * policy.missing_weight)
    )

    score = int((weighted_score / total) * 100)

    # Readiness classification from policy
    if score >= policy.min_ready_score:
        label = "Ready"
    elif score >= policy.min_near_ready_score:
        label = "Near Ready"
    else:
        label = "Not Ready"

    return JobFitScore(
        score=score,
        label=label,
        ok=ok,
        gap=gap,
        missing=missing,
    )


# ============================================================
# Career Blocking Factors (Explainability Engine)
# ============================================================

from dataclasses import dataclass
from typing import Optional, List


@dataclass(frozen=True)
class CareerBlockingFactor:
    code: str                     # stable identifier (for UI/filtering)
    title: str                    # human readable short title
    severity: str                 # "high" | "medium" | "low"
    details: str                  # short explanation
    skill: Optional[object] = None
    required_level: Optional[object] = None
    current_level: Optional[object] = None
    delta_progress: Optional[int] = None


def compute_career_blocking_factors(employee: Employee) -> list[CareerBlockingFactor]:
    """
    Enterprise best practice:
    - Explain WHY employee is Not Ready / Near Ready
    - Based on ACTIVE job requirements only (via compute_employee_job_gap)
    - Policy-driven readiness thresholds (via compute_employee_job_fit_score)
    - Produces stable codes for dashboards and analytics
    """
    if not employee:
        return []

    factors: list[CareerBlockingFactor] = []

    # Hard blocks first (governance)
    if not employee.active:
        factors.append(
            CareerBlockingFactor(
                code="employee_inactive",
                title="Employee is inactive",
                severity="high",
                details="Employee is archived/inactive, readiness is blocked.",
            )
        )
        return factors

    if not employee.job_id:
        factors.append(
            CareerBlockingFactor(
                code="no_job_assigned",
                title="No job assigned",
                severity="high",
                details="Employee has no job, so job requirements cannot be evaluated.",
            )
        )
        return factors

    # Policy-based fit score
    fit = compute_employee_job_fit_score(employee)

    # If policy missing, this is governance issue (should be fixed by admin)
    if fit.label == "No Career Policy":
        factors.append(
            CareerBlockingFactor(
                code="no_career_policy",
                title="No career policy",
                severity="high",
                details="No active career policy exists for this employee's company.",
            )
        )
        return factors

    # Job requirement gap analysis
    rows = compute_employee_job_gap(employee)

    if not rows:
        # No job requirements is not a blocker; but it's a governance signal
        factors.append(
            CareerBlockingFactor(
                code="no_job_requirements",
                title="No job requirements defined",
                severity="medium",
                details="This job has no required skills defined, so readiness is not evidence-based.",
            )
        )
        return factors

    missing_rows = [r for r in rows if r.status == "missing"]
    gap_rows = [r for r in rows if r.status == "gap"]

    # Highest severity: missing required skills
    for r in missing_rows:
        factors.append(
            CareerBlockingFactor(
                code="missing_required_skill",
                title="Missing required skill",
                severity="high",
                details="Employee does not have this required skill recorded.",
                skill=r.required_skill,
                required_level=r.required_level,
                current_level=None,
                delta_progress=None,
            )
        )

    # Medium severity: has skill but below required level
    for r in gap_rows:
        factors.append(
            CareerBlockingFactor(
                code="below_required_level",
                title="Below required level",
                severity="medium",
                details="Employee level is below the minimum required level.",
                skill=r.required_skill,
                required_level=r.required_level,
                current_level=r.employee_level,
                delta_progress=r.delta_progress,
            )
        )

    # If overall status is still Not Ready, add summary factor
    if fit.label == "Not Ready":
        factors.append(
            CareerBlockingFactor(
                code="low_fit_score",
                title="Low fit score",
                severity="high",
                details=f"Fit score ({fit.score}%) is below company thresholds.",
            )
        )
    elif fit.label == "Near Ready":
        factors.append(
            CareerBlockingFactor(
                code="near_ready",
                title="Near ready",
                severity="low",
                details=f"Fit score ({fit.score}%) is close to readiness threshold.",
            )
        )

    # Stable ordering: high -> medium -> low
    sev_rank = {"high": 0, "medium": 1, "low": 2}
    factors.sort(key=lambda x: (sev_rank.get(x.severity, 9), x.code))

    return factors


# ============================================================
# Training Recommendation Engine (Policy + Blocking Driven)
# ============================================================

@dataclass(frozen=True)
class TrainingRecommendation:
    skill: object
    required_level: object
    current_level: Optional[object]
    reason: str        # "missing" | "gap"
    priority: int      # 1 = critical, 2 = important
    blocking_code: str # link to blocking factor


def compute_training_recommendations(
    employee: Employee,
) -> List[TrainingRecommendation]:
    """
    Training Recommendation Engine (Enterprise Best Practice)

    Principles:
    - Driven by Career Blocking Factors
    - Only actionable items
    - Clear priority
    - Zero duplication
    """

    if not employee or not employee.job_id:
        return []

    # Step 1: Get blocking factors (source of truth)
    blockers = compute_career_blocking_factors(employee)

    # Step 2: Map skill gaps once
    gap_rows = compute_employee_job_gap(employee)
    gap_by_skill_id = {
        r.required_skill.id: r
        for r in gap_rows
        if r.status in ("missing", "gap")
    }

    recommendations: List[TrainingRecommendation] = []

    for blocker in blockers:
        code = blocker["code"]

        # -------------------------------
        # Missing skills → CRITICAL
        # -------------------------------
        if code == "missing_skills":
            for skill_name in blocker.get("skills", []):
                row = next(
                    (
                        r for r in gap_rows
                        if r.required_skill.name == skill_name
                        and r.status == "missing"
                    ),
                    None,
                )
                if not row:
                    continue

                recommendations.append(
                    TrainingRecommendation(
                        skill=row.required_skill,
                        required_level=row.required_level,
                        current_level=None,
                        reason="missing",
                        priority=1,
                        blocking_code="missing_skills",
                    )
                )

        # -------------------------------
        # Skill level gaps → IMPORTANT
        # -------------------------------
        elif code == "skill_level_gap":
            for item in blocker.get("skills", []):
                row = next(
                    (
                        r for r in gap_rows
                        if r.required_skill.name == item["skill"]
                        and r.status == "gap"
                    ),
                    None,
                )
                if not row:
                    continue

                recommendations.append(
                    TrainingRecommendation(
                        skill=row.required_skill,
                        required_level=row.required_level,
                        current_level=row.employee_level,
                        reason="gap",
                        priority=2,
                        blocking_code="skill_level_gap",
                    )
                )

    # Step 3: Sort (critical first, then alphabetical)
    recommendations.sort(
        key=lambda r: (r.priority, r.skill.name)
    )

    return recommendations



# ============================================================
# Employee Readiness Index (Policy + Timeline Driven)
# ============================================================

@dataclass(frozen=True)
class EmployeeReadiness:
    score: int
    status: str                # ready | near_ready | not_ready
    fit_score: int
    blocking_reason: Optional[str]
    blocking_factors: List[str]
    estimated_ready_months: Optional[int]  # None if already ready or unknown


def compute_employee_readiness(employee: Employee) -> EmployeeReadiness:
    """
    Employee Readiness Index (Enterprise Best Practice)

    Characteristics:
    - Policy-driven (no magic numbers)
    - Explainable (blocking factors)
    - Predictive (time to readiness)
    """

    # --------------------------------------------------
    # Hard blocks (non-negotiable)
    # --------------------------------------------------
    if not employee:
        return EmployeeReadiness(
            score=0,
            status="not_ready",
            fit_score=0,
            blocking_reason="employee_not_found",
            blocking_factors=["employee_not_found"],
            estimated_ready_months=None,
        )

    if not employee.active:
        return EmployeeReadiness(
            score=0,
            status="not_ready",
            fit_score=0,
            blocking_reason="employee_not_active",
            blocking_factors=["employee_not_active"],
            estimated_ready_months=None,
        )

    if not employee.job_id:
        return EmployeeReadiness(
            score=0,
            status="not_ready",
            fit_score=0,
            blocking_reason="no_job_assigned",
            blocking_factors=["no_job_assigned"],
            estimated_ready_months=None,
        )

    # --------------------------------------------------
    # Resolve policy (Company-level)
    # --------------------------------------------------
    policy = resolve_career_policy_for_employee(employee)
    if not policy:
        return EmployeeReadiness(
            score=0,
            status="not_ready",
            fit_score=0,
            blocking_reason="no_career_policy",
            blocking_factors=["no_career_policy"],
            estimated_ready_months=None,
        )

    # --------------------------------------------------
    # Fit score
    # --------------------------------------------------
    fit = compute_employee_job_fit_score(employee)
    score = fit.score

    # --------------------------------------------------
    # Blocking factors (root cause)
    # --------------------------------------------------
    blockers = compute_career_blocking_factors(employee)
    blocker_codes = [b["code"] for b in blockers]

    # --------------------------------------------------
    # Status classification (policy-driven)
    # --------------------------------------------------
    if score >= policy.min_ready_score:
        status = "ready"
    elif score >= policy.min_near_ready_score:
        status = "near_ready"
    else:
        status = "not_ready"

    # --------------------------------------------------
    # Timeline estimation (simple, explainable model)
    # --------------------------------------------------
    estimated_months: Optional[int] = None

    if status != "ready":
        months = 0

        for b in blockers:
            code = b["code"]

            # Enterprise assumptions (adjustable later):
            if code == "missing_skills":
                months += 6      # acquiring missing skill
            elif code == "skill_level_gap":
                months += 3      # leveling up existing skill
            elif code == "insufficient_experience":
                months += 6
            elif code == "policy_threshold":
                months += 2

        estimated_months = max(months, 1) if months else None

    return EmployeeReadiness(
        score=score,
        status=status,
        fit_score=score,
        blocking_reason=blocker_codes[0] if blocker_codes else None,
        blocking_factors=blocker_codes,
        estimated_ready_months=estimated_months,
    )



# ============================================================
# Succession Planning (Job-centric)
# ============================================================

@dataclass(frozen=True)
class SuccessionCandidate:
    employee: Employee
    readiness_score: int
    readiness_status: str


def compute_job_succession_candidates(job) -> list[SuccessionCandidate]:
    employees = (
        Employee.objects
        .filter(job=job, active=True)
        .select_related("job")
    )

    candidates: list[SuccessionCandidate] = []

    for emp in employees:
        readiness = compute_employee_readiness(emp)
        if readiness.status in ("ready", "near_ready"):
            candidates.append(
                SuccessionCandidate(
                    employee=emp,
                    readiness_score=readiness.score,
                    readiness_status=readiness.status,
                )
            )

    return sorted(candidates, key=lambda c: (-c.readiness_score, c.employee.name))


# ============================================================
# Team Readiness Summary (Manager-centric)
# ============================================================

@dataclass(frozen=True)
class TeamReadinessSummary:
    total: int
    ready: int
    near_ready: int
    not_ready: int


def compute_team_readiness(manager: Employee) -> TeamReadinessSummary:
    team = (
        manager.managed_employees
        .filter(active=True)
        .select_related("job")
    )

    ready = near_ready = not_ready = 0

    for emp in team:
        readiness = compute_employee_readiness(emp)
        if readiness.status == "ready":
            ready += 1
        elif readiness.status == "near_ready":
            near_ready += 1
        else:
            not_ready += 1

    total = ready + near_ready + not_ready

    return TeamReadinessSummary(
        total=total,
        ready=ready,
        near_ready=near_ready,
        not_ready=not_ready,
    )


# ============================================================
# Department Job-Fit Coverage (Tree-based, Odoo-like)
# ============================================================

def compute_department_job_fit_coverage(department) -> dict:
    """
    Odoo-like org KPI (Best Practice):
    - Department tree (department + children)
    - ACTIVE departments + ACTIVE employees only
    - Uses Job Fit Score (based on JobSkill requirements)
    Returns:
    {
        "employees": int,
        "avg_score": int,
        "excellent": int,   # >= 90
        "acceptable": int,  # 70..89
        "needs_training": int, # 40..69
        "not_fit": int,     # < 40
    }
    """
    if not department:
        return {
            "employees": 0,
            "avg_score": 0,
            "excellent": 0,
            "acceptable": 0,
            "needs_training": 0,
            "not_fit": 0,
        }

    dept_path = department.parent_path or ""
    DepartmentModel = type(department)

    departments = (
        DepartmentModel.objects
        .filter(parent_path__startswith=dept_path, active=True)
    )

    employees = (
        Employee.objects
        .filter(department__in=departments, active=True)
        .select_related("job")
    )

    if not employees.exists():
        return {
            "employees": 0,
            "avg_score": 0,
            "excellent": 0,
            "acceptable": 0,
            "needs_training": 0,
            "not_fit": 0,
        }

    excellent = acceptable = needs_training = not_fit = 0
    total_score = 0
    count = 0

    for emp in employees:
        # if no job -> skip from fit KPI (clean, enterprise)
        if not emp.job_id:
            continue

        fit = compute_employee_job_fit_score(emp)
        total_score += fit.score
        count += 1

        if fit.score >= 90:
            excellent += 1
        elif fit.score >= 70:
            acceptable += 1
        elif fit.score >= 40:
            needs_training += 1
        else:
            not_fit += 1

    if count == 0:
        return {
            "employees": employees.count(),
            "avg_score": 0,
            "excellent": 0,
            "acceptable": 0,
            "needs_training": 0,
            "not_fit": 0,
        }

    return {
        "employees": employees.count(),
        "avg_score": int(total_score / count),
        "excellent": excellent,
        "acceptable": acceptable,
        "needs_training": needs_training,
        "not_fit": not_fit,
    }


# ============================================================
# Department Risks (Tree-based, Job-fit driven)
# ============================================================

def compute_department_risks(department) -> dict:
    """
    Risk Indicators:
    - no_excellent_staff: no one >=90
    - manager_not_acceptable: manager fit <70
    """
    if not department:
        return {
            "no_excellent_staff": True,
            "manager_not_acceptable": False,
        }

    cov = compute_department_job_fit_coverage(department)
    no_excellent_staff = cov["excellent"] == 0

    manager_not_acceptable = False
    if getattr(department, "manager_id", None):
        mgr = department.manager
        if mgr and mgr.active and mgr.job_id:
            mgr_fit = compute_employee_job_fit_score(mgr)
            manager_not_acceptable = mgr_fit.score < 70

    return {
        "no_excellent_staff": no_excellent_staff,
        "manager_not_acceptable": manager_not_acceptable,
    }


# ============================================================
# Employee-skill coverage (Actual holders) – for SPOF
# ============================================================

def compute_department_employee_skill_coverage(department) -> dict:
    """
    Returns:
    { skill_name: number_of_active_employees_having_skill }
    Note:
    - department scope = EXACT department only (not tree) by design.
      If you want tree, pass department tree employees instead.
    """
    if not department:
        return {}

    qs = (
        EmployeeSkill.objects
        .filter(employee__department=department, employee__active=True, active=True)
        .select_related("skill", "employee")
    )

    coverage: dict[str, int] = {}
    for es in qs:
        if not es.skill_id:
            continue
        name = es.skill.name
        coverage[name] = coverage.get(name, 0) + 1

    return coverage


# ============================================================
# Single Point of Failure Indicator (SPOF)
# ============================================================

def compute_single_point_of_failure(department) -> dict:
    """
    Returns:
    {
        "skills": [skill names],
        "count": int
    }
    """
    coverage = compute_department_employee_skill_coverage(department)

    risky_skills = [
        skill for skill, count in coverage.items()
        if count == 1
    ]

    return {"skills": risky_skills, "count": len(risky_skills)}


# ============================================================
# Department Readiness Score (Simple KPI)
# ============================================================

def compute_department_readiness_score(department) -> dict:
    """
    Best Practice (simple + explainable):
    - Uses Job-Fit coverage average
    - Uses SPOF count as penalty

    Returns:
    { "score": int, "status": str }
    """
    cov = compute_department_job_fit_coverage(department)
    spof = compute_single_point_of_failure(department)

    # base = avg_score, penalty = 5 per SPOF skill (bounded)
    base = cov["avg_score"]
    penalty = min(spof["count"] * 5, 30)
    score = max(base - penalty, 0)

    if score >= 85:
        status = "ready"
    elif score >= 70:
        status = "attention"
    else:
        status = "critical"

    return {"score": score, "status": status}


# ============================================================
# Manager Action Hints
# ============================================================

def compute_department_action_hints(department) -> list[str]:
    actions: list[str] = []

    readiness = compute_department_readiness_score(department)
    spof = compute_single_point_of_failure(department)

    if readiness["status"] == "critical":
        actions.append("Immediate training or hiring required")

    if spof["count"] > 0:
        actions.append("Create backup for critical skills")

    if readiness["status"] == "ready" and spof["count"] == 0:
        actions.append("No action required")

    return actions


# ============================================================
# Succession Planning (Employee-centric)
# ============================================================

def compute_succession_candidates(target_employee, min_score: int = 70) -> list[dict]:
    """
    Identify internal successors for a critical role.
    - Same department tree
    - Active employees
    - Fit score >= min_score
    """
    if not target_employee or not target_employee.job_id:
        return []

    dept = target_employee.department
    dept_path = dept.parent_path or ""

    candidates = (
        Employee.objects
        .filter(department__parent_path__startswith=dept_path, active=True)
        .exclude(id=target_employee.id)
        .select_related("job")
    )

    results: list[dict] = []

    for emp in candidates:
        if not emp.job_id:
            continue

        fit = compute_employee_job_fit_score(emp)
        if fit.score >= min_score:
            results.append({
                "employee": emp,
                "fit_score": fit.score,
                "label": fit.label,
            })

    results.sort(key=lambda x: x["fit_score"], reverse=True)
    return results


# ============================================================
# Critical Position Risk Index
# ============================================================

def compute_position_risk(employee) -> dict:
    """
    Risk levels:
    - low | medium | high
    """
    if not employee or not employee.job_id:
        return {"risk": "unknown", "reason": "no_job_assigned"}

    fit = compute_employee_job_fit_score(employee)
    successors = compute_succession_candidates(employee)

    if fit.score < 50:
        return {"risk": "high", "reason": "low_skill_fit"}

    if not successors:
        return {"risk": "high", "reason": "no_successor"}

    if fit.score < 80:
        return {"risk": "medium", "reason": "partial_fit"}

    return {"risk": "low", "reason": "healthy_position"}


# ============================================================
# Career Path Eligibility (Policy + Explainable)
# ============================================================

def compute_employee_career_eligibility(employee) -> list:
    """
    Career Path Eligibility (Enterprise-grade)

    Decision is based on:
    - CareerPolicy thresholds
    - Job Fit Score
    - Blocking Factors (explainable)

    Output is audit-ready & UI-friendly.
    """

    if not employee or not employee.job_id:
        return []

    from hr.models import JobCareerPath

    # Resolve policy-driven fit score
    fit = compute_employee_job_fit_score(employee)

    # Explain WHY (if not eligible)
    blockers = compute_career_blocking_factors(employee)

    # Career paths from current job
    paths = (
        JobCareerPath.objects
        .filter(from_job=employee.job, active=True)
        .select_related("to_job")
        .order_by("sequence")
    )

    results = []

    for path in paths:
        eligible = fit.label == "Ready"

        results.append({
            "job": path.to_job,
            "current_job": employee.job,

            # Policy-driven values
            "required_score": (
                resolve_career_policy_for_employee(employee).min_ready_score
                if resolve_career_policy_for_employee(employee)
                else None
            ),
            "employee_score": fit.score,

            # Final decision
            "eligible": eligible,
            "status": fit.label,   # Ready | Near Ready | Not Ready

            # Explainability (CRITICAL)
            "blocking_factors": blockers if not eligible else [],
            "blocking_count": len(blockers),

            # Machine-readable reason
            "decision_reason": (
                "meets_policy_requirements"
                if eligible
                else "skill_gaps_detected"
            ),
        })

    return results


# ============================================================
# Career Blocking Factors (Explainable Decision)
# ============================================================

@dataclass(frozen=True)
class CareerBlockingFactor:
    skill: object
    required_level: object
    current_level: Optional[object]
    reason: str            # "missing" | "gap"
    delta_progress: Optional[int]


# ============================================================
# Career Blocking Factors (Explainable Readiness)
# ============================================================

def compute_career_blocking_factors(employee) -> list:
    """
    Explain WHY an employee is not Ready.

    Best Practice:
    - No magic logic
    - Fully explainable
    - Policy + Skill driven
    """

    if not employee or not employee.job_id:
        return [{
            "code": "no_job_assigned",
            "message": "Employee has no job assigned.",
        }]

    policy = resolve_career_policy_for_employee(employee)

    if not policy:
        return [{
            "code": "no_career_policy",
            "message": "No active career policy for company.",
        }]

    rows = compute_employee_job_gap(employee)

    blockers = []

    # 1️⃣ Missing required skills
    missing_skills = [
        r for r in rows if r.status == "missing"
    ]
    if missing_skills:
        blockers.append({
            "code": "missing_skills",
            "count": len(missing_skills),
            "skills": [r.required_skill.name for r in missing_skills],
            "message": "Employee is missing required job skills.",
        })

    # 2️⃣ Skill level gaps
    gap_skills = [
        r for r in rows if r.status == "gap"
    ]
    if gap_skills:
        blockers.append({
            "code": "skill_level_gap",
            "count": len(gap_skills),
            "skills": [
                {
                    "skill": r.required_skill.name,
                    "required": r.required_level.name,
                    "current": r.employee_level.name,
                }
                for r in gap_skills
            ],
            "message": "Employee does not meet minimum skill levels.",
        })

    # 3️⃣ Overall score below policy threshold
    fit = compute_employee_job_fit_score(employee)

    if fit.score < policy.min_ready_score:
        blockers.append({
            "code": "score_below_policy",
            "required_score": policy.min_ready_score,
            "employee_score": fit.score,
            "message": "Job fit score is below policy readiness threshold.",
        })

    return blockers


@dataclass(frozen=True)
class ReadinessTimelinePoint:
    date: object  # datetime.date
    score: int
    status: str
    fit_score: int


# ------------------

def create_employee_readiness_snapshot(employee: Employee, snapshot_date=None) -> EmployeeReadinessSnapshot:
    """
    Create/Upsert a snapshot for an employee on a given date.
    Best practice: idempotent daily/weekly run.
    """
    if not employee or not employee.company_id:
        raise ValueError("Employee and employee.company are required for readiness snapshot.")

    snapshot_date = snapshot_date or timezone.localdate()

    readiness = compute_employee_readiness(employee)
    policy = resolve_career_policy_for_employee(employee)

    obj, _created = EmployeeReadinessSnapshot.objects.update_or_create(
        employee_id=employee.id,
        snapshot_date=snapshot_date,
        defaults={
            "company_id": employee.company_id,
            "job_id": employee.job_id,
            "score": readiness.score,
            "status": readiness.status,
            "fit_score": readiness.fit_score,
            "blocking_reason": readiness.blocking_reason or "",
            "blocking_factors": readiness.blocking_factors or [],
            "policy_id": getattr(policy, "id", None),
        }
    )
    return obj


def get_employee_readiness_timeline(
    employee: Employee,
    days: int = 180,
) -> list[ReadinessTimelinePoint]:
    """
    Readiness timeline for charts/trends.

    - Pulls from snapshots only (enterprise best practice)
    - Fallback: if no snapshots exist, returns single point (today)
      WITHOUT writing to DB (safe for views).
    """
    if not employee:
        return []

    end_date = timezone.localdate()
    start_date = end_date - timedelta(days=days)

    qs = (
        EmployeeReadinessSnapshot.objects
        .filter(employee_id=employee.id, snapshot_date__gte=start_date, snapshot_date__lte=end_date)
        .order_by("snapshot_date")
        .only("snapshot_date", "score", "status", "fit_score")
    )

    if not qs.exists():
        # Fallback: compute once (no DB write)
        r = compute_employee_readiness(employee)
        return [
            ReadinessTimelinePoint(
                date=end_date,
                score=r.score,
                status=r.status,
                fit_score=r.fit_score,
            )
        ]

    return [
        ReadinessTimelinePoint(
            date=o.snapshot_date,
            score=o.score,
            status=o.status,
            fit_score=o.fit_score,
        )
        for o in qs
    ]


# ============================================================
# Employee Readiness Snapshot Service (Explicit Only)
# ============================================================

from django.utils import timezone
from hr.models import EmployeeReadinessSnapshot
from skills.services import (
    compute_employee_readiness,
    resolve_career_policy_for_employee,
    compute_career_blocking_factors,
)

def create_employee_readiness_snapshot(
    employee,
    reason: str,
):
    """
    Create immutable readiness snapshot.
    Called ONLY from explicit business events.

    Events:
    - Skill evaluation
    - Job change
    - Official review
    """

    if not employee or not employee.company_id:
        return None

    readiness = compute_employee_readiness(employee)
    policy = resolve_career_policy_for_employee(employee)

    snapshot = EmployeeReadinessSnapshot.objects.create(
        employee=employee,
        company=employee.company,
        job=employee.job,
        snapshot_date=timezone.localdate(),

        score=readiness.score,
        status=readiness.status,
        fit_score=readiness.fit_score,

        blocking_reason=readiness.blocking_reason or "",
        blocking_factors=compute_career_blocking_factors(employee),

        policy_id=policy.id if policy else None,
    )

    return snapshot
