# assets/access.py
# ============================================================
# Access Layer for Assets Application (ACL-only)
#
# IMPORTANT:
# - This module contains NO business rules.
# - All access decisions come entirely from ObjectACL via base.acl_service.has_perm.
# - Views should prefer QuerySets:
#       Model.acl_objects.with_acl("view")
#       Model.acl_objects.with_acl("change")
# - These helpers exist فقط كواجهة موحّدة للـ templates/services.
# ============================================================

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from base.acl_service import has_perm

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractBaseUser
    from assets.models import Asset, AssetCategory, AssetAssignment


# ============================================================
# Generic helper
# ============================================================

def _can(user: Optional["AbstractBaseUser"], obj, action: str) -> bool:
    """
    Thin ACL wrapper:
      - no business logic
      - no company / department rules
      - pure ACL lookup
    """
    return has_perm(obj, user, action)


# ============================================================
# Category
# ============================================================

def can_view_category(user, category: "AssetCategory") -> bool:
    return _can(user, category, "view")


def can_edit_category(user, category: "AssetCategory") -> bool:
    return _can(user, category, "change")


def can_delete_category(user, category: "AssetCategory") -> bool:
    return _can(user, category, "delete")


# ============================================================
# Asset
# ============================================================

def can_view_asset(user, asset: "Asset") -> bool:
    return _can(user, asset, "view")


def can_edit_asset(user, asset: "Asset") -> bool:
    return _can(user, asset, "change")


def can_delete_asset(user, asset: "Asset") -> bool:
    return _can(user, asset, "delete")


def can_assign_asset(user, asset: "Asset") -> bool:
    return _can(user, asset, "assign")


# ============================================================
# Assignment History
# ============================================================

def can_view_assignment(user, assignment: "AssetAssignment") -> bool:
    return _can(user, assignment, "view")


def can_edit_assignment(user, assignment: "AssetAssignment") -> bool:
    return _can(user, assignment, "change")


def can_delete_assignment(user, assignment: "AssetAssignment") -> bool:
    return _can(user, assignment, "delete")
