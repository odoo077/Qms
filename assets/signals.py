"""
Signals for the Assets app (STRICT + Odoo-like)

- No implicit re-assignments.
- No auto-creation of AssetAssignment from Asset changes.
- Close open assignments automatically when:
    * Asset becomes inactive
    * Asset status moves to maintenance/retired
- Enforce company + status/holder consistency.
"""

from __future__ import annotations

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from django.core.exceptions import ValidationError

from base.acl_service import apply_default_acl
from . import models as m
from .services import close_open_assignments_for_asset, NON_ASSIGNABLE_STATUSES


# =======================
# Category parent_path & ACL
# =======================

@receiver(pre_save, sender=m.AssetCategory)
def _cat_update_parent_path(sender, instance: m.AssetCategory, **kwargs):
    if instance.parent_id:
        try:
            parent = m.AssetCategory.objects.only("id", "parent_path").get(pk=instance.parent_id)
            prefix = parent.parent_path or ""
        except m.AssetCategory.DoesNotExist:
            prefix = ""
        instance.parent_path = f"{prefix}{instance.parent_id}/"
    else:
        instance.parent_path = ""


@receiver(post_save, sender=m.AssetCategory)
def _category_default_acl(sender, instance: m.AssetCategory, created: bool, **kwargs):
    if created:
        apply_default_acl(instance)


# =======================
# Asset strict consistency
# =======================

@receiver(pre_save, sender=m.Asset)
def _asset_company_and_state_consistency(sender, instance: m.Asset, **kwargs):
    """
    Enforce:
    - status/holder consistency
    - company consistency across related FKs
    - prevent manual re-assignment when open assignment exists
    - capture old values for downstream checks
    """
    # ---- capture old values ----
    old = None
    if instance.pk:
        old = m.Asset.objects.only("holder_id", "status", "active", "company_id").filter(pk=instance.pk).first()

    old_holder_id = old.holder_id if old else None
    old_status = old.status if old else None
    old_active = old.active if old else None
    old_company_id = old.company_id if old else None

    instance._old_holder_id = old_holder_id
    instance._old_status = old_status
    instance._old_active = old_active
    instance._old_company_id = old_company_id

    # ---- status/holder consistency ----
    if instance.status != m.Asset.Status.ASSIGNED and instance.holder_id:
        instance.holder = None

    if instance.status == m.Asset.Status.ASSIGNED and not instance.holder_id:
        instance.status = m.Asset.Status.AVAILABLE

    # ---- company consistency ----
    company_id = instance.company_id
    if company_id:
        if (
            instance.category_id and instance.category
            and getattr(instance.category, "company_id", None)
            and instance.category.company_id != company_id
        ):
            instance.category = None

        if (
            instance.department_id and instance.department
            and getattr(instance.department, "company_id", None)
            and instance.department.company_id != company_id
        ):
            instance.department = None

        if (
            instance.holder_id and instance.holder
            and getattr(instance.holder, "company_id", None)
            and instance.holder.company_id != company_id
        ):
            instance.holder = None
            instance.status = m.Asset.Status.AVAILABLE

    # ---- STRICT: منع إعادة الإسناد اليدوي ----
    # إذا كان الأصل Assigned ثم حاول أحدهم تغيير holder إلى موظف آخر مع بقاء Assigned
    # فهذا "Reassignment" ويجب أن يُمنع (إلا عبر unassign ثم assign)
    if old and old_status == m.Asset.Status.ASSIGNED and old_holder_id:
        if instance.status == m.Asset.Status.ASSIGNED and instance.holder_id and instance.holder_id != old_holder_id:
            raise ValidationError({
                "holder": "Re-assignment is not allowed. Unassign the asset first, then assign it again."
            })


@receiver(post_save, sender=m.Asset)
def _asset_close_open_assignments_on_non_assignable(sender, instance: m.Asset, created: bool, **kwargs):
    """
    Close open assignments when asset becomes non-assignable:
    - active -> False
    - status -> maintenance/retired
    """
    # New record: لا يوجد assignment سابق منطقيًا
    if created:
        return

    old_active = getattr(instance, "_old_active", None)
    old_status = getattr(instance, "_old_status", None)

    # 1) active became False
    if old_active is True and instance.active is False:
        close_open_assignments_for_asset(instance, reason="Asset deactivated")
        return

    # 2) status moved into NON_ASSIGNABLE_STATUSES
    if old_status and (old_status not in NON_ASSIGNABLE_STATUSES) and (instance.status in NON_ASSIGNABLE_STATUSES):
        close_open_assignments_for_asset(instance, reason=f"Status changed to {instance.status}")


@receiver(post_save, sender=m.Asset)
def _auto_archive_on_retired(sender, instance: m.Asset, **kwargs):
    """
    When asset status moves to RETIRED, automatically set active=False
    to mimic Odoo's auto-archive behavior.
    """
    if instance.status == m.Asset.Status.RETIRED and instance.active:
        sender.objects.filter(pk=instance.pk, active=True).update(active=False)


# =======================
# Assignment company consistency & ACL
# =======================

@receiver(pre_save, sender=m.AssetAssignment)
def _ensure_assignment_company_consistency(sender, instance: m.AssetAssignment, **kwargs):
    """
    Keep AssetAssignment.company aligned with Asset.company.
    """
    if instance.asset_id:
        asset = getattr(instance, "asset", None)
        if asset and getattr(asset, "company_id", None):
            instance.company_id = asset.company_id


@receiver(post_save, sender=m.Asset)
def _asset_default_acl(sender, instance: m.Asset, created: bool, **kwargs):
    if created:
        apply_default_acl(instance)


@receiver(post_save, sender=m.AssetAssignment)
def _assetassignment_default_acl(sender, instance: m.AssetAssignment, created: bool, **kwargs):
    if created:
        apply_default_acl(instance)
