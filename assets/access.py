# assets/access.py
# ------------------------------------------------------------
# Best-Practice Access Layer for Assets Application
# ------------------------------------------------------------
# IMPORTANT:
# - This module contains NO business rules.
# - All access decisions come entirely from ACL (ObjectACL).
# - Views should rely on:
#       Model.acl_objects.with_acl("view")
#       Model.acl_objects.with_acl("change")
# - The only job of these functions is to provide a clean
#   standard interface used by templates or services.
# ------------------------------------------------------------

from __future__ import annotations
from django.contrib.auth import get_user_model

from assets.models import Asset, AssetCategory, AssetAssignment
from base.acl_service import has_perm

User = get_user_model()


# ============================================================
# Generic helpers
# ============================================================

def _can(user: User, obj, action: str) -> bool:
    """
    A thin wrapper over ACL:
      - No business logic here.
      - No department or employee logic.
      - Pure ACL lookup.
    """
    return has_perm(obj, user, action)


# ============================================================
# Category
# ============================================================

def can_view_category(user: User, category: AssetCategory) -> bool:
    return _can(user, category, "view")


def can_edit_category(user: User, category: AssetCategory) -> bool:
    return _can(user, category, "change")


def can_delete_category(user: User, category: AssetCategory) -> bool:
    return _can(user, category, "delete")


# ============================================================
# Asset
# ============================================================

def can_view_asset(user: User, asset: Asset) -> bool:
    return _can(user, asset, "view")


def can_edit_asset(user: User, asset: Asset) -> bool:
    return _can(user, asset, "change")


def can_delete_asset(user: User, asset: Asset) -> bool:
    return _can(user, asset, "delete")


def can_assign_asset(user: User, asset: Asset) -> bool:
    return _can(user, asset, "assign")


# ============================================================
# Assignment History
# ============================================================

def can_view_assignment(user: User, assignment: AssetAssignment) -> bool:
    return _can(user, assignment, "view")


def can_edit_assignment(user: User, assignment: AssetAssignment) -> bool:
    return _can(user, assignment, "change")


def can_delete_assignment(user: User, assignment: AssetAssignment) -> bool:
    return _can(user, assignment, "delete")
