# assets/signals.py
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
from django.core.exceptions import ValidationError

from . import models as m
from .services import close_open_assignments_for_asset, NON_ASSIGNABLE_STATUSES


# ============================================================
# AssetCategory: parent_path maintenance
# ============================================================

@receiver(pre_save, sender=m.AssetCategory)
def _cat_update_parent_path(sender, instance: m.AssetCategory, **kwargs):
    """
    Maintain parent_path for hierarchical categories.
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


# ============================================================
# Asset: strict consistency enforcement
# ============================================================

@receiver(pre_save, sender=m.Asset)
def _asset_company_and_state_consistency(sender, instance: m.Asset, **kwargs):
    """
    Enforce:
    - status / holder consistency
    - company consistency across related FKs
    - prevent manual re-assignment when open assignment exists
    - capture old values for downstream checks
    """
    # --------------------------------------------------
    # Capture old values
    # --------------------------------------------------
    old = None
    if instance.pk:
        old = (
            m.Asset.objects
            .only("holder_id", "status", "active", "company_id")
            .filter(pk=instance.pk)
            .first()
        )

    instance._old_holder_id = old.holder_id if old else None
    instance._old_status = old.status if old else None
    instance._old_active = old.active if old else None
    instance._old_company_id = old.company_id if old else None

    # --------------------------------------------------
    # Status ↔ Holder consistency
    # --------------------------------------------------
    if instance.status != m.Asset.Status.ASSIGNED and instance.holder_id:
        instance.holder = None

    if instance.status == m.Asset.Status.ASSIGNED and not instance.holder_id:
        instance.status = m.Asset.Status.AVAILABLE

    # --------------------------------------------------
    # Company consistency across relations
    # --------------------------------------------------
    company_id = instance.company_id
    if company_id:
        if (
            instance.category_id
            and instance.category
            and getattr(instance.category, "company_id", None) != company_id
        ):
            instance.category = None

        if (
            instance.department_id
            and instance.department
            and getattr(instance.department, "company_id", None) != company_id
        ):
            instance.department = None

        if (
            instance.holder_id
            and instance.holder
            and getattr(instance.holder, "company_id", None) != company_id
        ):
            instance.holder = None
            instance.status = m.Asset.Status.AVAILABLE

    # --------------------------------------------------
    # STRICT: منع إعادة الإسناد اليدوي
    # --------------------------------------------------
    if old and old.status == m.Asset.Status.ASSIGNED and old.holder_id:
        if (
            instance.status == m.Asset.Status.ASSIGNED
            and instance.holder_id
            and instance.holder_id != old.holder_id
        ):
            raise ValidationError({
                "holder": (
                    "Re-assignment is not allowed. "
                    "Unassign the asset first, then assign it again."
                )
            })


# ============================================================
# Asset: auto-close assignments on non-assignable state
# ============================================================

@receiver(post_save, sender=m.Asset)
def _asset_close_open_assignments_on_non_assignable(
    sender,
    instance: m.Asset,
    created: bool,
    **kwargs,
):
    """
    Close open assignments when asset becomes non-assignable:
    - active -> False
    - status -> maintenance / retired
    """
    if created:
        return

    old_active = getattr(instance, "_old_active", None)
    old_status = getattr(instance, "_old_status", None)

    # 1) Asset deactivated
    if old_active is True and instance.active is False:
        close_open_assignments_for_asset(
            instance,
            reason="Asset deactivated",
        )
        return

    # 2) Status moved into NON_ASSIGNABLE_STATUSES
    if (
        old_status
        and old_status not in NON_ASSIGNABLE_STATUSES
        and instance.status in NON_ASSIGNABLE_STATUSES
    ):
        close_open_assignments_for_asset(
            instance,
            reason=f"Status changed to {instance.status}",
        )


# ============================================================
# Asset: auto-archive on retired
# ============================================================

@receiver(post_save, sender=m.Asset)
def _auto_archive_on_retired(sender, instance: m.Asset, **kwargs):
    """
    When asset status moves to RETIRED, automatically set active=False
    to mimic Odoo's auto-archive behavior.
    """
    if instance.status == m.Asset.Status.RETIRED and instance.active:
        sender.objects.filter(
            pk=instance.pk,
            active=True,
        ).update(active=False)


# ============================================================
# AssetAssignment: company consistency
# ============================================================

@receiver(pre_save, sender=m.AssetAssignment)
def _ensure_assignment_company_consistency(
    sender,
    instance: m.AssetAssignment,
    **kwargs,
):
    """
    Keep AssetAssignment.company aligned with Asset.company.
    """
    if instance.asset_id:
        asset = getattr(instance, "asset", None)
        if asset and getattr(asset, "company_id", None):
            instance.company_id = asset.company_id
