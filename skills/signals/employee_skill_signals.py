from django.db.models.signals import pre_save
from django.dispatch import receiver
from skills.models import HrEmployeeSkill
from django.core.exceptions import ValidationError
from datetime import date

@receiver(pre_save, sender=HrEmployeeSkill)
def prevent_overlap_employee_skill(sender, instance, **kwargs):
    qs = HrEmployeeSkill.objects.filter(
        employee=instance.employee, skill=instance.skill
    ).exclude(pk=instance.pk)

    start1, end1 = instance.valid_from, instance.valid_to or date.max
    for rec in qs:
        start2, end2 = rec.valid_from, rec.valid_to or date.max
        if max(start1, start2) <= min(end1, end2) and not instance.is_certification:
            raise ValidationError("Overlapping skill validity not allowed for non-certifications.")


@receiver(pre_save, sender=HrEmployeeSkill)
def validate_employee_skill(sender, instance, **kwargs):
    # Ensure valid_from < valid_to if both provided
    if instance.valid_from and instance.valid_to and instance.valid_from > instance.valid_to:
        raise ValueError("valid_from cannot be later than valid_to")