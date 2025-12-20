# assets/signals.py
"""
Signals for the Assets app

Goals:
- Keep hierarchy / company consistency (Odoo-like behavior).
- Automatically manage AssetAssignment records when holder/status changes.
- Auto-archive retired assets.
- Apply default ACL (apply_default_acl) for newly created records so that:
    - Owner (created_by) gets full access.
    - HR managers get full access.
    - Department hierarchy managers get operational access.
    - Asset holders and assignment employees get the correct rights.
"""

from __future__ import annotations

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from base.acl_service import apply_default_acl
from . import models as m


# =======================
# Category parent_path & ACL
# =======================

@receiver(pre_save, sender=m.AssetCategory)
def _cat_update_parent_path(sender, instance: m.AssetCategory, **kwargs):
    """
    Maintain a materialized parent_path for fast hierarchy queries
    (similar to Odoo parent_path behavior).
    """
    if instance.parent_id:
        try:
            parent = (
                m.AssetCategory.objects
                .only("id", "parent_path")
                .get(pk=instance.parent_id)
            )
            prefix = parent.parent_path or ""
        except m.AssetCategory.DoesNotExist:
            prefix = ""
        instance.parent_path = f"{prefix}{instance.parent_id}/"
    else:
        instance.parent_path = ""


@receiver(post_save, sender=m.AssetCategory)
def _category_default_acl(sender, instance: m.AssetCategory, created: bool, **kwargs):
    """
    Apply default ACL only on creation.
    """
    if created:
        apply_default_acl(instance)


# =======================
# Asset company consistency & assignment logic
# =======================

@receiver(pre_save, sender=m.Asset)
def _asset_company_and_state_consistency(sender, instance: m.Asset, **kwargs):
    """
    Ensure company + status + holder consistency:

    - If status is not ASSIGNED → clear holder.
    - If status is ASSIGNED but no holder → fallback to AVAILABLE.
    - Ensure related FK objects belong to the same company:
        * category from another company → cleared
        * department from another company → cleared
        * holder from another company → cleared + status=AVAILABLE

    Also store old holder & status on the instance (for existing records)
    so post_save can manage assignment logs (AssetAssignment) correctly.
    """
    # ------------------------------------------------------------
    # (0) Capture old values (existing records only)
    # ------------------------------------------------------------
    if instance.pk:
        try:
            old: m.Asset = m.Asset.objects.only("holder_id", "status", "company_id").get(pk=instance.pk)
        except m.Asset.DoesNotExist:
            old = None

        if old:
            instance._old_holder_id = old.holder_id
            instance._old_status = old.status
            old_company_id = old.company_id
        else:
            instance._old_holder_id = None
            instance._old_status = None
            old_company_id = None
    else:
        instance._old_holder_id = None
        instance._old_status = None
        old_company_id = None

    # ------------------------------------------------------------
    # (1) Status/holder consistency (applies for new + existing)
    # ------------------------------------------------------------
    if instance.status != m.Asset.Status.ASSIGNED and instance.holder_id:
        instance.holder = None

    if instance.status == m.Asset.Status.ASSIGNED and not instance.holder_id:
        instance.status = m.Asset.Status.AVAILABLE

    # ------------------------------------------------------------
    # (2) Company consistency (applies for new + existing)
    #     - For existing: we only need to re-check aggressively when company changed,
    #       but it's safe to enforce always.
    # ------------------------------------------------------------
    # If company changed, we must ensure cross-company links are cleared.
    # If new record, we also enforce correctness.
    company_id = instance.company_id
    if company_id:
        # 1) category from another company? clear it
        if (
            instance.category_id
            and instance.category
            and getattr(instance.category, "company_id", None)
            and instance.category.company_id != company_id
        ):
            instance.category = None

        # 2) department from another company? clear it
        if (
            instance.department_id
            and instance.department
            and getattr(instance.department, "company_id", None)
            and instance.department.company_id != company_id
        ):
            instance.department = None

        # 3) holder from another company? clear it + set status to AVAILABLE
        if (
            instance.holder_id
            and instance.holder
            and getattr(instance.holder, "company_id", None)
            and instance.holder.company_id != company_id
        ):
            instance.holder = None
            instance.status = m.Asset.Status.AVAILABLE

    # If company changed, ensure we also don't keep an "ASSIGNED" status with cleared holder.
    if old_company_id is not None and old_company_id != company_id:
        if instance.status == m.Asset.Status.ASSIGNED and not instance.holder_id:
            instance.status = m.Asset.Status.AVAILABLE


@receiver(post_save, sender=m.Asset)
def _asset_auto_assignment_on_holder_change(sender, instance: m.Asset, created: bool, **kwargs):
    """
    Automatically maintain AssetAssignment records based on holder/status changes:

    - On creation or update:
        * If holder or status changed:
            - Close open assignment for old holder (date_to = today).
            - If new holder + status=ASSIGNED and no open assignment → create one.
    """
    today = timezone.localdate()

    old_holder_id = getattr(instance, "_old_holder_id", None)
    old_status = getattr(instance, "_old_status", None)

    new_holder_id = instance.holder_id
    new_status = instance.status

    changed = created or (old_holder_id != new_holder_id) or (old_status != new_status)
    if not changed:
        return

    # 1) close open assignment for previous holder (if it should be closed)
    if old_holder_id:
        open_qs = m.AssetAssignment.objects.filter(
            asset=instance,
            employee_id=old_holder_id,
            date_to__isnull=True,
            active=True,
        )
        if (new_holder_id != old_holder_id) or (new_status != m.Asset.Status.ASSIGNED):
            open_qs.update(date_to=today)

    # 2) create new assignment for new holder (only if assigned)
    if new_holder_id and (new_status == m.Asset.Status.ASSIGNED):
        exists = m.AssetAssignment.objects.filter(
            asset=instance,
            employee_id=new_holder_id,
            date_to__isnull=True,
            active=True,
        ).exists()
        if not exists:
            m.AssetAssignment.objects.create(
                asset=instance,
                employee_id=new_holder_id,
                company=instance.company,
                date_from=today,
                note="Auto-created from Asset change",
            )


@receiver(post_save, sender=m.Asset)
def _auto_archive_on_retired(sender, instance: m.Asset, **kwargs):
    """
    When asset status moves to RETIRED, automatically set active=False
    to mimic Odoo's auto-archive behavior.

    Implementation detail:
    - Use queryset.update() to avoid recursive saves/signals.
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
    (Odoo-like: company consistency enforcement without hard errors).
    """
    if instance.asset_id:
        # accessing instance.asset is acceptable هنا لأننا داخل form scoped غالبًا،
        # وهذا يحافظ على التوافق حتى عند الإنشاء من scripts.
        asset = getattr(instance, "asset", None)
        if asset and getattr(asset, "company_id", None):
            instance.company_id = asset.company_id


@receiver(post_save, sender=m.Asset)
def _asset_default_acl(sender, instance: m.Asset, created: bool, **kwargs):
    """
    Apply default ACL when an Asset is created.
    """
    if created:
        apply_default_acl(instance)


@receiver(post_save, sender=m.AssetAssignment)
def _assetassignment_default_acl(sender, instance: m.AssetAssignment, created: bool, **kwargs):
    """
    Apply default ACL when an AssetAssignment is created.
    """
    if created:
        apply_default_acl(instance)
