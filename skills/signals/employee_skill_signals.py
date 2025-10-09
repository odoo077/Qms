# skills/signals/employee_skill_signals.py
from datetime import date
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.core.exceptions import ValidationError
from django.db.models import Q
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
