from django.db.models.signals import post_delete
from django.db.models.signals import post_migrate
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_save
from django.dispatch import receiver
from guardian.shortcuts import assign_perm
from django.contrib.auth import get_user_model
from assets.models import AssetItem, EmployeeAsset

User = get_user_model()


@receiver(post_delete, sender=EmployeeAsset)
def reset_item_after_delete(sender, instance: EmployeeAsset, **kwargs):
    item = instance.item
    # لو لم يبقَ تسليم نشط، صفّر الحامل وأعد الحالة
    other = EmployeeAsset.objects.filter(item=item, is_active=True).values_list("employee_id", flat=True).first()
    item.current_employee_id = other or None
    if not other and item.status == "assigned":
        item.status = "in_stock"
    item.save(update_fields=["current_employee", "status"])

# --------- ownership & roles -------

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

@receiver(post_migrate)
def ensure_asset_groups_and_perms(sender, **kwargs):
    # تأكد أن الإشارة تعمل عند ترحيل تطبيق الأصول فقط
    if getattr(sender, "name", None) != "assets":
        return

    # 1) أنشئ/اجلب مجموعة Asset Officers
    group, _ = Group.objects.get_or_create(name="Asset Officers")

    # 2) اجلب ContentTypes
    ct_item = ContentType.objects.get_for_model(AssetItem)
    ct_assign = ContentType.objects.get_for_model(EmployeeAsset)

    # 3) صلاحيات موديل EmployeeAsset
    needed_codenames = [
        ("add_employeeasset", ct_assign),
        ("change_employeeasset", ct_assign),
        ("view_employeeasset", ct_assign),
        # (يمكن إضافة delete_employeeasset لاحقًا إن احتجته)
    ]

    # 4) صلاحيات موديل/كائن AssetItem (الموديل + المخصصة)
    needed_codenames += [
        ("view_assetitem", ct_item),
        ("change_assetitem", ct_item),
        ("assign_item", ct_item),
        ("return_item", ct_item),
        ("transfer_item", ct_item),
    ]

    perms = []
    for codename, ct in needed_codenames:
        try:
            perm = Permission.objects.get(codename=codename, content_type=ct)
            perms.append(perm)
        except Permission.DoesNotExist:
            # في حال تأخر إنشاء Permission (نادرًا)، يمكن تجاهلها وسيُعاد استدعاء post_migrate
            continue

    if perms:
        group.permissions.add(*perms)
