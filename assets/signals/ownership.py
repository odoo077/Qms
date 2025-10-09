from django.db.models.signals import post_save
from django.dispatch import receiver
from guardian.shortcuts import assign_perm
from django.contrib.auth import get_user_model
from assets.models import AssetItem, EmployeeAsset

User = get_user_model()


@receiver(post_save, sender=AssetItem)
def grant_owner_perms_item(sender, instance, created, **kwargs):
    """إسناد صلاحيات العرض والتعديل لمنشئ الأصل عند إنشائه."""
    if created and hasattr(instance, "created_by") and instance.created_by:
        user = instance.created_by
        assign_perm("assets.view_assetitem", user, instance)
        assign_perm("assets.change_assetitem", user, instance)
        assign_perm("assets.assign_item", user, instance)


@receiver(post_save, sender=EmployeeAsset)
def grant_owner_perms_assignment(sender, instance, created, **kwargs):
    if created and instance.created_by:
        user = instance.created_by
        assign_perm("assets.view_employeeasset", user, instance)
        assign_perm("assets.change_employeeasset", user, instance)
        assign_perm("assets.delete_employeeasset", user, instance)
