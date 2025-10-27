# -*- coding: utf-8 -*-
"""
خدمات (Domain Services) للأصول
- دوال إسناد/إلغاء إسناد الأصول بشكل موحّد وآمن
- منح/إدارة صلاحيات Guardian على مستوى الكائن (يوزرات معيّنة) عبر نقاط إدخال جاهزة
"""

from __future__ import annotations
from typing import Optional, Iterable
from datetime import date

from django.contrib.auth import get_user_model
from django.db import transaction
from django.core.exceptions import ValidationError

from base.acl_service import grant_access, revoke_access

from . import models as m

User = get_user_model()

# ------------------------------------------------------------
# صلاحيات الكائن (Guardian) – أسماء الصلاحيات القياسية من Django:
#   view_asset, change_asset, delete_asset | view_assetcategory ... إلخ
# يمكنك توسيع منطق المنح هنا إذا رغبت.
# ------------------------------------------------------------

def grant_default_object_perms(asset: m.Asset, users: Iterable[User]) -> None:
    """
    منح الصلاحيات الافتراضية لمجموعة مستخدمين على أصل معيّن عبر نظام الـACL.
    """
    for u in users:
        grant_access(asset, user=u, view=True, change=True, delete=True)


def revoke_all_object_perms(asset: m.Asset, users: Iterable[User]) -> None:
    """
    سحب جميع صلاحيات الكائن (يحذف ACE) للمستخدمين المحددين.
    """
    for u in users:
        revoke_access(asset, user=u)  # حذف السطر بالكامل للمستخدم



# ------------------------------------------------------------
# منطق الإسناد
# ------------------------------------------------------------

@transaction.atomic
def assign_asset(asset: m.Asset, employee_id: int, *, date_from: Optional[date] = None, note: str = "") -> m.AssetAssignment:
    """
    إسناد أصل لموظف:
    - إنشاء سجل إسناد جديد
    - تحديث حامل الأصل والحالة
    - لا يتعارض مع إسنادات سابقة (يغلق القديمة إذا لزم)
    """
    if asset.status == m.Asset.Status.RETIRED:
        raise ValidationError("Cannot assign a retired asset.")

    # أغلق أي اسناد سابق مفتوح لنفس الأصل
    latest_open = asset.assignments.filter(date_to__isnull=True, active=True).order_by("-id").first()
    if latest_open:
        latest_open.date_to = date_from or date.today()
        latest_open.save(update_fields=["date_to"])

    asg = m.AssetAssignment.objects.create(
        asset=asset,
        employee_id=employee_id,
        company=asset.company,
        date_from=date_from or date.today(),
        note=note,
        active=True,
    )

    asset.holder_id = employee_id
    asset.status = m.Asset.Status.ASSIGNED
    asset.save(update_fields=["holder_id", "status", "updated_at"])
    return asg


@transaction.atomic
def unassign_asset(asset: m.Asset, *, date_to: Optional[date] = None, note: str = "") -> None:
    """
    إلغاء إسناد أصل:
    - إغلاق آخر إسناد مفتوح
    - إرجاع الأصل إلى الحالة Available
    """
    latest_open = asset.assignments.filter(date_to__isnull=True, active=True).order_by("-id").first()
    if not latest_open:
        return
    latest_open.date_to = date_to or date.today()
    if note:
        latest_open.note = (latest_open.note + " | " + note).strip(" |")
    latest_open.save(update_fields=["date_to", "note"])

    asset.holder = None
    asset.status = m.Asset.Status.AVAILABLE
    asset.save(update_fields=["holder_id", "status", "updated_at"])
