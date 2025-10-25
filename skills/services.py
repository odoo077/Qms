# skills/services.py
# ============================================================
# Services for Skills app (Odoo-like)
# - طبقة خدمات للتعامل مع SkillType/SkillLevel/Skill/EmployeeSkill/ResumeLine
# - متوافقة مع signals (guardian) + منطق الحقول في models.py
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

# ------------------------------------------------------------
# Dynamic model getters (تجنب دورات الاستيراد المباشر)
# ------------------------------------------------------------
SkillType = apps.get_model("skills", "SkillType")
SkillLevel = apps.get_model("skills", "SkillLevel")
Skill = apps.get_model("skills", "Skill")
EmployeeSkill = apps.get_model("skills", "EmployeeSkill")
ResumeLineType = apps.get_model("skills", "ResumeLineType")
ResumeLine = apps.get_model("skills", "ResumeLine")
Employee = apps.get_model("hr", "Employee")


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
        return
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
    - signals ستمنح صلاحيات guardian تلقائيًا للـ created_by والـ employee.user.
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
    - صلاحيات الكائن تُدار عبر Guardian/Signals خارج هذه الدالة.
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
    - signals تمنح صلاحيات العرض/التعديل للـ created_by + عرض للموظف.user.
    """
    # تاريخ منطقي
    if data.date_start and data.date_end and data.date_end < data.date_start:
        raise ValidationError({"date_end": "Date to must be after or equal to Date from."})

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
    قائمة مهارات ضمن شركة محددة (Odoo-like scoping).
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
