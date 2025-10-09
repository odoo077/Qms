# assets/signals/roles.py
from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

from assets.models import AssetItem, EmployeeAsset

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
