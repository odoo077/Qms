from django.db.models.signals import post_save
from django.dispatch import receiver
from guardian.shortcuts import assign_perm
from skills.models import HrEmployeeSkill

@receiver(post_save, sender=HrEmployeeSkill)
def grant_owner_perms_skill(sender, instance, created, **kwargs):
    if created and getattr(instance, "created_by", None):
        user = instance.created_by
        assign_perm("skills.view_employeeskill", user, instance)
        assign_perm("skills.change_employeeskill", user, instance)
        assign_perm("skills.rate_skill", user, instance)
