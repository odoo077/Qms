# xfield/access.py
# ------------------------------------------------------------
# Business rules for the dynamic fields system (xfield).
#
# DOES NOT:
#   - assign or check ObjectACL permissions
#   - depend on fixed roles / groups
#   - use any non-existing models/fields
#
# ONLY:
#   - uses XField / XFieldOption / XValue as defined in xfield/models.py
#   - uses Employee + company scope utilities from base.access
# ------------------------------------------------------------

from __future__ import annotations

from typing import Optional

from django.contrib.auth import get_user_model

from hr.models import Employee
from xfields.models import XField, XFieldOption, XValue
from base.access import get_employee, is_in_same_company

User = get_user_model()


# ============================================================
# Helpers
# ============================================================

def _get_xvalue_company_id(xvalue: XValue) -> Optional[int]:
    """
    Determine the company scope for an XValue.

    Priority:
      1) XField.company (if set)
      2) target.company_id (if the target model has that field)
      3) None if no company is detectable
    """
    # 1) Company from XField itself (optional in your model)
    xf_company_id = getattr(xvalue.field, "company_id", None)
    if xf_company_id:
        return xf_company_id

    # 2) Company from the target object (GenericForeignKey)
    target_obj = getattr(xvalue, "target", None)
    return getattr(target_obj, "company_id", None)


# ============================================================
# 1) XField rules
# ============================================================

def can_view_xfield(user: User, xfield: XField) -> bool:
    """
    A dynamic field definition is viewable if:
      - user is authenticated
      - and:
        * either xfield.company is NULL (global field)
        * or user is within the same company scope
    """
    if not user or not user.is_authenticated:
        return False

    # Global fields (no company restriction)
    if xfield.company_id is None:
        return True

    # Company-scoped fields
    return is_in_same_company(user, xfield.company_id)


def can_edit_xfield(user: User, xfield: XField) -> bool:
    """
    High-level business rule (NOT ACL):
      - editing allowed only for users within the same company scope
        (for company-specific fields).
      - for global fields, any authenticated user may be allowed
        (ACL will still be the final authority).
    """
    if not user or not user.is_authenticated:
        return False

    if xfield.company_id is None:
        # Global field: allow authenticated users, ACL will further restrict.
        return True

    # Company-scoped: must be inside same company scope
    return is_in_same_company(user, xfield.company_id)


# ============================================================
# 2) XFieldOption rules
# ============================================================

def can_view_xfield_option(user: User, option: XFieldOption) -> bool:
    """
    Viewable if the parent XField is viewable.
    """
    return can_view_xfield(user, option.field)


def can_edit_xfield_option(user: User, option: XFieldOption) -> bool:
    """
    Editable if the parent XField is editable.
    """
    return can_edit_xfield(user, option.field)


# ============================================================
# 3) XValue rules
# ============================================================

def can_view_xvalue(user: User, xvalue: XValue) -> bool:
    """
    A value record is viewable if:

      - user is authenticated, and
      - company scope check passes (if a company can be determined), and
      - for Employee targets:
          * self
          * or direct manager
          * or manager in the chain

    NOTE:
      - This is pure business logic.
      - Actual permissions remain enforced by ACL on the target model.
    """
    if not user or not user.is_authenticated:
        return False

    company_id = _get_xvalue_company_id(xvalue)
    if company_id is not None:
        if not is_in_same_company(user, company_id):
            return False

    # If the target is an Employee, add hierarchy-based rules
    target_obj = getattr(xvalue, "target", None)
    if isinstance(target_obj, Employee):
        me = get_employee(user)
        if not me:
            return False

        # Self
        if target_obj.id == me.id:
            return True

        # Manager (direct or in chain)
        # NOTE: use business logic from HR via base.access if needed later.
        # Here we simply allow managers via the same employee object
        # without duplicating ACL.
        from base.access import is_manager_of, user_is_in_manager_chain

        if is_manager_of(user, target_obj):
            return True

        if user_is_in_manager_chain(user, target_obj):
            return True

        # Same company but no other relation → default False here
        return False

    # For non-Employee targets:
    # if company scope passed (or no company detected), allow viewing.
    return True


def can_edit_xvalue(user: User, xvalue: XValue) -> bool:
    """
    Editing rules:

      - user must pass company scope (if detectable)
      - if target is Employee:
          * employee can edit their own xfields
          * managers (direct or in chain) can edit
      - for other targets:
          * rely only on company scope (ACL will enforce final edit rights)
    """
    if not user or not user.is_authenticated:
        return False

    company_id = _get_xvalue_company_id(xvalue)
    if company_id is not None and not is_in_same_company(user, company_id):
        return False

    target_obj = getattr(xvalue, "target", None)
    if isinstance(target_obj, Employee):
        me = get_employee(user)
        if not me:
            return False

        # Self-edit
        if target_obj.id == me.id:
            return True

        # Manager editing
        from base.access import is_manager_of, user_is_in_manager_chain

        if is_manager_of(user, target_obj):
            return True

        if user_is_in_manager_chain(user, target_obj):
            return True

        return False

    # Non-Employee targets:
    # company scope (if any) is enough as a high-level rule.
    # ACL will still decide the actual permission.
    return True
