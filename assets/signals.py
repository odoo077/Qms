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

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.utils import timezone

from base.acl_service import apply_default_acl
from . import models as m

User = get_user_model()


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
    Apply default ACL only on creation:
    - owner + HR managers + hierarchy rules (if any dept logic is defined later).
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
    - If company changes:
        * category from another company → cleared
        * department from another company → cleared
        * holder from another company → cleared + status=AVAILABLE

    Also store old holder & status on the instance so post_save can
    manage assignment logs (AssetAssignment) correctly.
    """
    if not instance.pk:
        # No previous state yet, nothing to compare with
        return

    try:
        old: m.Asset = m.Asset.objects.get(pk=instance.pk)
    except m.Asset.DoesNotExist:
        return

    # keep previous holder & status for post_save
    instance._old_holder_id = old.holder_id
    instance._old_status = old.status

    # status/holder consistency
    if instance.status != m.Asset.Status.ASSIGNED and instance.holder_id:
        # if no longer ASSIGNED, clear the holder to keep state consistent
        instance.holder = None

    if instance.status == m.Asset.Status.ASSIGNED and not instance.holder_id:
        # avoid broken state "Assigned with no holder": downgrade to AVAILABLE
        instance.status = m.Asset.Status.AVAILABLE

    # company consistency
    if old.company_id != instance.company_id:
        # 1) category from another company? clear it
        if (
            instance.category_id
            and instance.category
            and instance.category.company_id
            and instance.category.company_id != instance.company_id
        ):
            instance.category = None

        # 2) department from another company? clear it
        if (
            instance.department_id
            and instance.department
            and instance.department.company_id
            and instance.department.company_id != instance.company_id
        ):
            instance.department = None

        # 3) holder from another company? clear it + set status to AVAILABLE
        if (
            instance.holder_id
            and instance.holder
            and instance.holder.company_id
            and instance.holder.company_id != instance.company_id
        ):
            instance.holder = None
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
    today = timezone.now().date()

    old_holder_id = getattr(instance, "_old_holder_id", None)
    old_status = getattr(instance, "_old_status", None)
    new_holder_id = instance.holder_id
    new_status = instance.status

    # Trigger only if we have creation or relevant changes
    changed = created or (old_holder_id != new_holder_id) or (old_status != new_status)
    if not changed:
        return

    # 1) close open assignment for previous holder
    if old_holder_id:
        open_qs = m.AssetAssignment.objects.filter(
            asset=instance,
            employee_id=old_holder_id,
            date_to__isnull=True,
            active=True,
        )
        if (new_holder_id != old_holder_id) or (new_status != m.Asset.Status.ASSIGNED):
            open_qs.update(date_to=today)

    # 2) create new assignment for new holder
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
    """
    if instance.status == m.Asset.Status.RETIRED and instance.active:
        instance.active = False
        # This save will re-trigger post_save, but the condition will be false next time
        instance.save(update_fields=["active"])


# =======================
# Assignment company consistency & ACL
# =======================

@receiver(pre_save, sender=m.AssetAssignment)
def _ensure_assignment_company_consistency(sender, instance: m.AssetAssignment, **kwargs):
    """
    Keep AssetAssignment.company aligned with Asset.company.
    (Odoo-like: company consistency enforcement without hard errors).
    """
    if instance.asset_id and instance.asset.company_id:
        instance.company_id = instance.asset.company_id


@receiver(post_save, sender=m.Asset)
def _asset_default_acl(sender, instance: m.Asset, created: bool, **kwargs):
    """
    Apply default ACL when an Asset is created:
    - Owner, HR managers, dept hierarchy, holder ACL, etc.
    (implemented inside base.acl_service.apply_default_acl).
    """
    if created:
        apply_default_acl(instance)


@receiver(post_save, sender=m.AssetAssignment)
def _assetassignment_default_acl(sender, instance: m.AssetAssignment, created: bool, **kwargs):
    """
    Apply default ACL when an AssetAssignment is created:
    - Employee gets view on assignment + view/change on the underlying Asset.
    """
    if created:
        apply_default_acl(instance)
