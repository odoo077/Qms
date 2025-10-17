# skills/services/employee_skill_service.py
from __future__ import annotations
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional, Dict, Any

from django.db import transaction
from django.core.exceptions import ValidationError
from django.apps import apps
from django.db.models import Q


HrEmployeeSkill = apps.get_model("skills", "HrEmployeeSkill")
HrSkill = apps.get_model("skills", "HrSkill")
HrSkillLevel = apps.get_model("skills", "HrSkillLevel")
HrSkillType = apps.get_model("skills", "HrSkillType")


DATE_MAX = date(9999, 12, 31)


def _yesterday(d: date) -> date:
    return d - timedelta(days=1)


def _normalize_dates(valid_from: date, valid_to: Optional[date]) -> tuple[date, Optional[date]]:
    if not valid_from:
        raise ValidationError({"valid_from": "valid_from is required."})
    if valid_to and valid_from > valid_to:
        raise ValidationError({"valid_to": "valid_to must be on or after valid_from."})
    return valid_from, valid_to


def _ensure_skill_coherence(skill_type_id: int, skill_id: int, level_id: int):
    """تحقق أن (skill, level) يتبعان skill_type نفسه."""
    st = HrSkillType.objects.only("id").get(pk=skill_type_id)
    s = HrSkill.objects.only("id", "skill_type_id").get(pk=skill_id)
    lv = HrSkillLevel.objects.only("id", "skill_type_id").get(pk=level_id)
    if s.skill_type_id != st.id:
        raise ValidationError({"skill": "Skill must belong to the selected skill type."})
    if lv.skill_type_id != st.id:
        raise ValidationError({"skill_level": "Level must belong to the selected skill type."})


def _exact_duplicate_exists(employee_id: int, skill_id: int, level_id: int, valid_from: date, valid_to: Optional[date]) -> bool:
    """يتحقق هل هناك سجل مطابق 100% (نفس employee/skill/level/period)."""
    qs = HrEmployeeSkill.objects.filter(
        employee_id=employee_id, skill_id=skill_id, skill_level_id=level_id, valid_from=valid_from
    )
    if valid_to is None:
        qs = qs.filter(valid_to__isnull=True)
    else:
        qs = qs.filter(valid_to=valid_to)
    return qs.exists()


def _close_open_non_certification(employee_id: int, skill_id: int, cutoff: date, exclude_pk: Optional[int] = None):
    """
    يغلق أي سجلات مفتوحة/متداخلة للمهارة العادية لنفس الموظف والمهارة
    عبر ضبط valid_to = cutoff (عادةً يوم قبل valid_from الجديد).
    """
    qs = HrEmployeeSkill.objects.filter(employee_id=employee_id, skill_id=skill_id)
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    # أغلِق كل ما يمتد بعد cutoff أو مفتوح للنهاية
    qs.filter(Q(valid_to__isnull=True) | Q(valid_to__gt=cutoff)).update(valid_to=cutoff)


def _overlap_exists_for_non_certification(employee_id: int, skill_id: int, valid_from: date, valid_to: Optional[date], exclude_pk: Optional[int] = None) -> bool:
    """
    يتحقق من وجود تداخل لفترة مهارة "عادية" لنفس الموظف والمهارة.
    """
    v_to = valid_to or DATE_MAX
    qs = HrEmployeeSkill.objects.filter(employee_id=employee_id, skill_id=skill_id)
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    return qs.filter(
        Q(valid_from__lte=v_to) & (Q(valid_to__isnull=True) | Q(valid_to__gte=valid_from))
    ).exists()


@transaction.atomic
def add_skill(
    *,
    employee_id: int,
    skill_type_id: int,
    skill_id: int,
    level_id: int,
    valid_from: date,
    valid_to: Optional[date] = None,
) -> HrEmployeeSkill:
    """
    إنشاء سجل مهارة للموظف وفق منطق Odoo:
    - لو Certification: يُسمح بالتعدد بفترات مختلفة (مع منع التطابق 100%).
    - لو غير شهادة: ممنوع التداخل → نغلق القديم إن وُجد، ثم ننشئ الجديد.
    """
    # 1) تحقق التواريخ والتناسق
    valid_from, valid_to = _normalize_dates(valid_from, valid_to)
    _ensure_skill_coherence(skill_type_id, skill_id, level_id)

    st = HrSkillType.objects.only("id", "is_certification").get(pk=skill_type_id)
    is_cert = st.is_certification

    # 2) منع التطابق 100%
    if _exact_duplicate_exists(employee_id, skill_id, level_id, valid_from, valid_to):
        raise ValidationError("Exact duplicate employee skill already exists.")

    # 3) معالجة المهارات العادية (non-certification)
    if not is_cert:
        # ممنوع التداخل
        if _overlap_exists_for_non_certification(employee_id, skill_id, valid_from, valid_to):
            # قبل الإنشاء، أغلق أي سجلات مفتوحة أو متداخلة على cutoff = valid_from - 1
            cutoff = _yesterday(valid_from)
            _close_open_non_certification(employee_id, skill_id, cutoff)
        # (بعد الإغلاق لن يعود هناك تداخل)

    # 4) الإنشاء الفعلي
    rec = HrEmployeeSkill.objects.create(
        employee_id=employee_id,
        skill_type_id=skill_type_id,
        skill_id=skill_id,
        skill_level_id=level_id,
        valid_from=valid_from,
        valid_to=valid_to,
    )
    return rec


@transaction.atomic
def update_skill_versioned(instance: HrEmployeeSkill, **changes: Any) -> HrEmployeeSkill:
    """
    تعديل سجل مهارة وفق منطق Odoo (Versioned write):
    - لا نعدّل السجل نفسه؛ نُغلِق القديم وننشئ سجلًا جديدًا بالقيم المعدلة.
    - لو Certification: يُسمح بالتعدد، لكن نمنع التطابق 100%.
    - لو غير شهادة: نمنع التداخل، عبر إغلاق القديم قبل إنشاء الجديد.
    المدخلات في **changes** يمكن أن تتضمن أيًا من:
        skill_type_id / skill_id / skill_level_id / valid_from / valid_to
    وأي حقول أخرى مستقبلية.
    """
    employee_id = instance.employee_id
    # استخرج القيم النهائية (القديمة + التغييرات)
    skill_type_id = changes.get("skill_type_id", instance.skill_type_id)
    skill_id = changes.get("skill_id", instance.skill_id)
    level_id = changes.get("skill_level_id", instance.skill_level_id)
    valid_from = changes.get("valid_from", instance.valid_from)
    valid_to = changes.get("valid_to", instance.valid_to)

    # تحقق التواريخ والتناسق
    valid_from, valid_to = _normalize_dates(valid_from, valid_to)
    _ensure_skill_coherence(skill_type_id, skill_id, level_id)

    st = HrSkillType.objects.only("id", "is_certification").get(pk=skill_type_id)
    is_cert = st.is_certification

    # منع التطابق 100% مع أي سجل آخر
    if _exact_duplicate_exists(employee_id, skill_id, level_id, valid_from, valid_to):
        # لو كان المطابق هو نفس السجل الحالي (نفس الفترة/القيم) لا داعي لإنشاء نسخة
        same = (
            instance.skill_type_id == skill_type_id and
            instance.skill_id == skill_id and
            instance.skill_level_id == level_id and
            instance.valid_from == valid_from and
            instance.valid_to == valid_to
        )
        if same:
            return instance  # لا تغيير
        raise ValidationError("Exact duplicate employee skill already exists.")

    # لو مهارة عادية → أغلق القديم ويُنشأ سجل جديد غير متداخل
    if not is_cert:
        cutoff = _yesterday(valid_from)
        _close_open_non_certification(employee_id, skill_id, cutoff, exclude_pk=instance.pk)

    # أغلق السجل الحالي إن كان مفتوحًا أو يمتد بعد cutoff (مهارات عادية) أو حسب رغبتك للشهادات (احتفاظ بالأرشيف)
    # في Odoo غالبًا يُغلق القديم عند أي تعديل ذو معنى.
    if instance.valid_to is None or instance.valid_to >= valid_from:
        instance.valid_to = _yesterday(valid_from)
        instance.save(update_fields=["valid_to"])

    # أنشئ النسخة الجديدة بالقيم المعدلة
    new_rec = HrEmployeeSkill.objects.create(
        employee_id=employee_id,
        skill_type_id=skill_type_id,
        skill_id=skill_id,
        skill_level_id=level_id,
        valid_from=valid_from,
        valid_to=valid_to,
    )
    return new_rec


@transaction.atomic
def archive_skill(instance: HrEmployeeSkill, valid_to: Optional[date] = None) -> HrEmployeeSkill:
    """
    إغلاق سجل مهارة يدويًا (أرشفة): يحدد valid_to (اليوم-1 افتراضيًا إن لم يمرّر).
    """
    if instance.valid_to:
        return instance  # مُغلق مسبقًا
    valid_to = valid_to or _yesterday(date.today())
    if valid_to < instance.valid_from:
        raise ValidationError({"valid_to": "Archive date must be on or after valid_from."})
    instance.valid_to = valid_to
    instance.save(update_fields=["valid_to"])
    return instance
