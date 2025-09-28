from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from skills.models import HrSkillLevel, HrSkillType

@receiver([post_save, post_delete], sender=HrSkillLevel)
def update_skilltype_levels_count(sender, instance, **kwargs):
    skill_type = instance.skill_type
    count = HrSkillLevel.objects.filter(skill_type=skill_type).count()
    HrSkillType.objects.filter(pk=skill_type.pk).update(levels_count=count)
