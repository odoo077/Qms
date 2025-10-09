# skills/signals/skill_signals.py
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db import transaction
from django.apps import apps


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
