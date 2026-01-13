# assets/services.py
"""
Domain Services للأصول (Odoo-like strict behavior)

- assign_asset / unassign_asset: هي نقطة الحقيقة الوحيدة للإسناد.
- close_open_assignments_for_asset: إغلاق العهدة المفتوحة عند حالات لا تسمح بالإسناد.
"""

from __future__ import annotations
from typing import Optional
from datetime import date

from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone

from . import models as m


# ------------------------------------------------------------
# Status policy
# ------------------------------------------------------------
NON_ASSIGNABLE_STATUSES = {
    m.Asset.Status.MAINTENANCE,
    m.Asset.Status.RETIRED,
}


# ------------------------------------------------------------
# Assignment helpers
# ------------------------------------------------------------
@transaction.atomic
def close_open_assignments_for_asset(
    asset: m.Asset,
    *,
    close_date: Optional[date] = None,
    reason: str = "",
) -> int:
    """
    يغلق أي AssetAssignment مفتوح للأصل:
    - Open = date_to is null
    Returns: عدد السجلات التي تم إغلاقها.
    """
    close_date = close_date or timezone.localdate()

    qs = (
        m.AssetAssignment.objects
        .select_for_update()
        .filter(asset=asset, date_to__isnull=True)
    )

    count = 0
    for asg in qs:
        asg.date_to = close_date
        if reason:
            base_note = (asg.note or "").strip()
            asg.note = (
                base_note
                + ("\n" if base_note else "")
                + f"Auto-closed: {reason}"
            )[:255]
        asg.save(update_fields=["date_to", "note"])
        count += 1

    return count


# ------------------------------------------------------------
# Core commands (source of truth)
# ------------------------------------------------------------
@transaction.atomic
def assign_asset(
    asset: m.Asset,
    employee_id: int,
    *,
    date_from: Optional[date] = None,
    note: str = "",
) -> m.AssetAssignment:
    """
    Assign asset to employee (STRICT):
    - Only if asset.active=True AND asset.status=AVAILABLE
    - Must have NO open assignment
    - Creates AssetAssignment then updates Asset(holder/status)
    """
    if not asset.active:
        raise ValidationError("Cannot assign an inactive asset.")

    if asset.status != m.Asset.Status.AVAILABLE:
        raise ValidationError(
            f"Cannot assign asset while status is '{asset.status}'. "
            "Asset must be in 'Available' status."
        )

    if m.AssetAssignment.objects.filter(
        asset=asset,
        date_to__isnull=True,
    ).exists():
        raise ValidationError("Asset already has an open assignment.")

    asg = m.AssetAssignment.objects.create(
        asset=asset,
        employee_id=employee_id,
        company=asset.company,
        date_from=date_from or timezone.localdate(),
        note=(note or "")[:255],
    )

    asset.holder_id = employee_id
    asset.status = m.Asset.Status.ASSIGNED
    asset.save(update_fields=["holder_id", "status", "updated_at"])

    return asg


@transaction.atomic
def unassign_asset(
    asset: m.Asset,
    *,
    date_to: Optional[date] = None,
    note: str = "",
) -> None:
    """
    Unassign asset (STRICT):
    - closes the single open assignment (if any)
    - sets Asset.holder=None and status=AVAILABLE
    """
    latest_open = (
        m.AssetAssignment.objects
        .select_for_update()
        .filter(asset=asset, date_to__isnull=True)
        .order_by("-id")
        .first()
    )

    if not latest_open:
        return

    latest_open.date_to = date_to or timezone.localdate()
    if note:
        base_note = (latest_open.note or "").strip()
        latest_open.note = (
            base_note
            + (" | " if base_note else "")
            + note
        )[:255]
    latest_open.save(update_fields=["date_to", "note"])

    asset.holder = None
    asset.status = m.Asset.Status.AVAILABLE
    asset.save(update_fields=["holder_id", "status", "updated_at"])
