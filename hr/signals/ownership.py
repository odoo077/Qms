from django.db.models.signals import post_save
from django.dispatch import receiver
from guardian.shortcuts import assign_perm
from hr.models import Employee

@receiver(post_save, sender=Employee)
def grant_owner_perms_employee(sender, instance, created, **kwargs):
    if created and getattr(instance, "created_by", None):
        user = instance.created_by
        assign_perm("hr.view_employee", user, instance)
        assign_perm("hr.change_employee", user, instance)
        assign_perm("hr.approve_employee", user, instance)
