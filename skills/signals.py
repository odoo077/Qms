from datetime import date
from django.db.models.signals import pre_save
from django.core.exceptions import ValidationError
from django.db.models import Q
from guardian.shortcuts import assign_perm
from django.db.models.signals import post_migrate
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from skills.models import HrEmployeeSkill  # عدّل الاسم حسب ملفك
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db import transaction
from django.apps import apps




HrEmployeeSkill = apps.get_model("skills", "HrEmployeeSkill")
DATE_MAX = date(9999, 12, 31)


@receiver(pre_save, sender=HrEmployeeSkill)
def employee_skill_pre_save(sender, instance: HrEmployeeSkill, **kwargs):
    """
    قبل الحفظ: تحقق أساسي + منع التداخل للمهارات غير الشهادات.
    (النسخ/الإغلاق يتم في الـ Service، لكن هذا يحمي من الكتابة غير المنضبطة بالـ ORM)
    """
    # استدعاء clean() (يضمن تناسق النوع/المهارة/المستوى وصحة التواريخ)
    instance.clean()

    # السماح بتعدد سجلات الشهادات بفترات مختلفة (منع تطابق 100% يتم في الخدمة)
    if instance.is_certification:
        return

    # منع التداخل للمهارات العادية
    v_from = instance.valid_from
    v_to = instance.valid_to or DATE_MAX

    overlapping = (HrEmployeeSkill.objects
                   .filter(employee_id=instance.employee_id, skill_id=instance.skill_id)
                   .exclude(pk=instance.pk)
                   .filter(Q(valid_from__lte=v_to) & (Q(valid_to__isnull=True) | Q(valid_to__gte=v_from))))
    if overlapping.exists():
        raise ValidationError({
            "valid_from": "Overlapping skill period for the same employee and skill is not allowed (non-certification).",
            "valid_to": "Please close the previous record or adjust dates.",
        })

# ------ skills signals ---------

def _recompute_levels_count(skill_type_id: int):
    HrSkillType = apps.get_model("skills", "HrSkillType")
    HrSkillLevel = apps.get_model("skills", "HrSkillLevel")

    try:
        st = HrSkillType.objects.get(pk=skill_type_id)
    except HrSkillType.DoesNotExist:
        return

    total = HrSkillLevel.objects.filter(skill_type_id=skill_type_id).count()
    if st.levels_count != total:
        st.levels_count = total
        st.save(update_fields=["levels_count"])


@receiver(post_save, sender=apps.get_model("skills", "HrSkillLevel"))
def skill_level_post_save(sender, instance, created, **kwargs):
    """
    بعد حفظ مستوى مهارة:
    - أعِد حساب levels_count على نوع المهارة المعني.
    """
    skill_type_id = instance.skill_type_id

    def _do():
        _recompute_levels_count(skill_type_id)

    try:
        transaction.on_commit(_do)
    except Exception:
        _do()


@receiver(post_delete, sender=apps.get_model("skills", "HrSkillLevel"))
def skill_level_post_delete(sender, instance, **kwargs):
    """
    بعد حذف مستوى مهارة:
    - أعِد حساب levels_count على نوع المهارة المعني.
    """
    skill_type_id = instance.skill_type_id
    _recompute_levels_count(skill_type_id)

# ------- ownership & roles signals --------

@receiver(post_save, sender=HrEmployeeSkill)
def grant_owner_perms_skill(sender, instance, created, **kwargs):
    if created and getattr(instance, "created_by", None):
        user = instance.created_by
        assign_perm("skills.view_employeeskill", user, instance)
        assign_perm("skills.change_employeeskill", user, instance)
        assign_perm("skills.rate_skill", user, instance)


@receiver(post_migrate)
def ensure_skills_roles(sender, **kwargs):
    if getattr(sender, "name", None) != "skills":
        return

    GROUPS = {
        "Skills Managers": [
            ("rate_skill", HrEmployeeSkill),
            ("view_employeeskill", HrEmployeeSkill),
            ("change_employeeskill", HrEmployeeSkill),
        ],
        "Skills Officers": [
            ("view_employeeskill", HrEmployeeSkill),
        ],
    }

    for group_name, entries in GROUPS.items():
        group, _ = Group.objects.get_or_create(name=group_name)
        for codename, model in entries:
            ct = ContentType.objects.get_for_model(model)
            try:
                perm = Permission.objects.get(codename=codename, content_type=ct)
                group.permissions.add(perm)
            except Permission.DoesNotExist:
                continue
