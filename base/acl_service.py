# base/acl_service.py
# ============================================================
# Global Object ACL Service (matches base/acl.py)
#
# - Single source of truth for object-level permissions across ALL apps.
# - Uses ObjectACL (ACE rows) with:
#     * Core flags: view/change/delete/share/approve/assign/comment/export/rate/attach
#     * extra_perms: free-text permissions (list[str]) for extensibility.
#
# Notes:
# - grant_access(): upsert ACE and updates only provided flags (None = keep as-is).
# - revoke_access(): delete ACE or revoke selected perms only.
# - has_perm(): object ACL check (user + groups). Company/privacy scope is handled by QuerySet.with_acl(...)
# - apply_default_acl(): default additive policy (Odoo-like) for newly created/updated objects.
# - TEAM VISIBILITY: incremental rebuild (per affected manager team) to avoid full rebuild overhead.
# ============================================================

from __future__ import annotations

from collections import defaultdict
from functools import lru_cache
from typing import Iterable, Optional, Sequence, Tuple

from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .acl import ObjectACL

# --------------------------------------------------------------------------------------
# Quick notes:
# - This module is intentionally import-safe: HR models are resolved lazily via apps.get_model().
# - Do not import hr.models directly here.
# --------------------------------------------------------------------------------------


# ======================================================================================
# HR model resolvers (lazy)
# ======================================================================================

@lru_cache(maxsize=1)
def _hr_models():
    Department = apps.get_model("hr", "Department")
    Employee = apps.get_model("hr", "Employee")
    return Department, Employee


def _employee_ct() -> ContentType:
    _, Employee = _hr_models()
    return ContentType.objects.get_for_model(Employee, for_concrete_model=False)


# ======================================================================================
# Core mapping / helpers
# ======================================================================================

_CORE_FLAG_BY_NAME = ObjectACL.CORE_FLAG_BY_NAME  # name -> field (e.g. "view" -> "can_view")


def _ct_and_pk(obj) -> Tuple[ContentType, int]:
    return ContentType.objects.get_for_model(obj, for_concrete_model=False), obj.pk


def _principal_filter(user=None, group=None) -> Q:
    q = Q()
    if user is not None:
        q &= Q(user=user)
    if group is not None:
        q &= Q(group=group)
    return q


def _normalize_extras(extras: Optional[Iterable[str]]) -> list[str]:
    if not extras:
        return []
    out: set[str] = set()
    for x in extras:
        x = (x or "").strip().lower()
        if x:
            out.add(x)
    return sorted(out)


# ======================================================================================
# Grant / Revoke
# ======================================================================================

def grant_access(
    obj,
    *,
    user=None,
    group=None,
    # Core flags: None = keep, True/False = set
    view: Optional[bool] = None,
    change: Optional[bool] = None,
    delete: Optional[bool] = None,
    share: Optional[bool] = None,
    approve: Optional[bool] = None,
    assign: Optional[bool] = None,
    comment: Optional[bool] = None,
    export: Optional[bool] = None,
    rate: Optional[bool] = None,
    attach: Optional[bool] = None,
    # Extras
    extras: Optional[Iterable[str]] = None,
    # Admin fields
    active: Optional[bool] = None,
    company=None,
):
    """
    Upsert ACE for (obj, principal), update ONLY the passed flags (non-None),
    and merge extra_perms.
    """
    ct, pk = _ct_and_pk(obj)

    core_defaults = {
        "can_view": bool(view) if view is not None else False,
        "can_change": bool(change) if change is not None else False,
        "can_delete": bool(delete) if delete is not None else False,
        "can_share": bool(share) if share is not None else False,
        "can_approve": bool(approve) if approve is not None else False,
        "can_assign": bool(assign) if assign is not None else False,
        "can_comment": bool(comment) if comment is not None else False,
        "can_export": bool(export) if export is not None else False,
        "can_rate": bool(rate) if rate is not None else False,
        "can_attach": bool(attach) if attach is not None else False,
    }
    extras_list = _normalize_extras(extras)

    defaults = {
        "active": True if active is None else bool(active),
        "company": company,
        **core_defaults,
    }
    if extras_list:
        defaults["extra_perms"] = extras_list

    ace, _ = ObjectACL.objects.get_or_create(
        content_type=ct,
        object_id=pk,
        user=user,
        group=group,
        defaults=defaults,
    )

    # Update only provided flags
    core_updates = {
        "can_view": view,
        "can_change": change,
        "can_delete": delete,
        "can_share": share,
        "can_approve": approve,
        "can_assign": assign,
        "can_comment": comment,
        "can_export": export,
        "can_rate": rate,
        "can_attach": attach,
    }
    for field_name, maybe_value in core_updates.items():
        if maybe_value is not None:
            setattr(ace, field_name, bool(maybe_value))

    # Merge extras
    new_extras = _normalize_extras(extras)
    if new_extras:
        current = set(ace.extra_perms or [])
        current.update(new_extras)
        ace.extra_perms = sorted(current)

    if active is not None:
        ace.active = bool(active)
    if company is not None:
        ace.company = company

    ace.save()
    return ace


def revoke_access(
    obj,
    *,
    user=None,
    group=None,
    only: Optional[Sequence[str]] = None,
    keep_row_if_empty: bool = False,
):
    """
    Revoke access:
      - If only is None/empty -> delete ACE row(s) for principal.
      - If only provided -> revoke selected perms (core/extra) and delete row if becomes empty
        unless keep_row_if_empty=True.
    """
    ct, pk = _ct_and_pk(obj)
    qs = ObjectACL.objects.filter(content_type=ct, object_id=pk).filter(_principal_filter(user, group))

    if not only:
        return qs.delete()

    names = [(n or "").strip().lower() for n in only if (n or "").strip()]
    if not names:
        return None

    for ace in qs:
        # Core flags
        for name in names:
            flag = _CORE_FLAG_BY_NAME.get(name)
            if flag:
                setattr(ace, flag, False)

        # Extras
        if ace.extra_perms:
            ace.extra_perms = sorted(x for x in ace.extra_perms if x not in names)

        still_has = (
            ace.can_view or ace.can_change or ace.can_delete or ace.can_share or
            ace.can_approve or ace.can_assign or ace.can_comment or ace.can_export or
            ace.can_rate or ace.can_attach or bool(ace.extra_perms)
        )

        if still_has or keep_row_if_empty:
            ace.save()
        else:
            ace.delete()

    return None


# ======================================================================================
# Checks / listing
# ======================================================================================

def has_perm(obj, user, action: str) -> bool:
    """
    Object ACL check only (user + groups).
    Company/privacy scope should be applied via QuerySet.with_acl(...) in base/acl.py.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True

    action = (action or "").strip().lower()
    ct, pk = _ct_and_pk(obj)

    group_ids = list(user.groups.values_list("id", flat=True))
    q = Q(content_type=ct, object_id=pk, active=True) & (Q(user=user) | Q(group_id__in=group_ids))

    flag, extra = ObjectACL.normalize_action(action)
    if flag:
        q &= Q(**{flag: True})
    else:
        q &= Q(extra_perms__contains=[extra])

    return ObjectACL.objects.filter(q).exists()


def list_access(obj):
    ct, pk = _ct_and_pk(obj)
    return ObjectACL.objects.filter(content_type=ct, object_id=pk)


# ======================================================================================
# Convenience helpers
# ======================================================================================

def set_access(
    obj,
    *,
    user=None,
    group=None,
    perms: Optional[Iterable[str]] = None,
    active: Optional[bool] = None,
    company=None,
):
    """
    Replace permission set for a principal on an object (keeps row).
    """
    ct, pk = _ct_and_pk(obj)
    ace, _ = ObjectACL.objects.get_or_create(
        content_type=ct,
        object_id=pk,
        user=user,
        group=group,
        defaults={"active": True if active is None else bool(active), "company": company},
    )

    # Reset all core flags
    for flag in _CORE_FLAG_BY_NAME.values():
        setattr(ace, flag, False)

    extras_set = set()

    if perms:
        for name in perms:
            name = (name or "").strip().lower()
            if not name:
                continue
            flag = _CORE_FLAG_BY_NAME.get(name)
            if flag:
                setattr(ace, flag, True)
            else:
                extras_set.add(name)

    ace.extra_perms = sorted(extras_set)

    if active is not None:
        ace.active = bool(active)
    if company is not None:
        ace.company = company

    ace.save()
    return ace


def grant_bulk(objs: Iterable, *, user=None, group=None, perms: Iterable[str] | None = None):
    """
    Grant a permission set to multiple objects.
    """
    perms = list(perms or [])
    core_kwargs = {}
    extras: list[str] = []

    for p in perms:
        p = (p or "").strip().lower()
        if not p:
            continue
        flag = _CORE_FLAG_BY_NAME.get(p)
        if flag:
            core_kwargs[flag.replace("can_", "")] = True  # "can_view" -> view=True
        else:
            extras.append(p)

    for obj in objs:
        grant_access(obj, user=user, group=group, extras=extras, **core_kwargs)


# ======================================================================================
# Default global policy (Odoo-style) - additive rules
# ======================================================================================

def _get_base_department_for_obj(obj):
    """
    Resolve base department for hierarchical ACL without isinstance() to avoid import-order issues.
    """
    meta = getattr(obj, "_meta", None)
    app_label = getattr(meta, "app_label", "")
    model_name = getattr(meta, "model_name", "")

    # obj itself is Department
    if app_label == "hr" and model_name == "department":
        return obj

    # direct FK: department
    if getattr(obj, "department_id", None):
        return getattr(obj, "department", None)

    # FK: employee -> department
    if getattr(obj, "employee_id", None):
        emp = getattr(obj, "employee", None)
        if emp and getattr(emp, "department_id", None):
            return getattr(emp, "department", None)

    return None


def apply_default_acl(obj, *, created: bool = False, old_employee_id: int | None = None):
    """
    Default ACL Rules applied on ANY saved object (additive only).

    GLOBAL:
    1) Owner (created_by) -> full access
    2) HR Managers (permission: hr.manage_all_hr) -> full access
    3) Employee -> view + change on his own Employee record
    4) Department manager hierarchy for related department -> view/change/approve/assign
    5) Department coordination:
       - manager of this department gets view-only on parents
       - sibling managers get view-only on this department

    APP-SPECIFIC:
    - skills:
        * employee.user -> view
        * owner -> view+change (+ rate for EmployeeSkill)
        * transfer view from old employee on reassignment
    - assets:
        * Asset.holder.user -> view+change
        * AssetAssignment.employee.user -> view on assignment + view+change on asset
    - performance:
        * Evaluation.employee.user -> view
    """
    # Nothing to apply on objects without PK
    if not getattr(obj, "pk", None):
        return

    Department, Employee = _hr_models()

    # (1) Owner
    owner = getattr(obj, "created_by", None)
    if owner:
        grant_access(
            obj,
            user=owner,
            view=True, change=True, delete=True,
            approve=True, assign=True, share=True,
        )

    # (1.1) Skills objects (EmployeeSkill / ResumeLine)
    try:
        meta = getattr(obj, "_meta", None)
        app_label = getattr(meta, "app_label", "")
        model_name = getattr(meta, "model_name", "")

        if app_label == "skills" and model_name in ("employeeskill", "resumeline"):
            emp = getattr(obj, "employee", None)
            emp_user = getattr(emp, "user", None) if emp else None

            if owner:
                grant_access(obj, user=owner, view=True, change=True)
                if model_name == "employeeskill":
                    grant_access(obj, user=owner, rate=True)

            if emp_user:
                grant_access(obj, user=emp_user, view=True)

            if old_employee_id and old_employee_id != getattr(obj, "employee_id", None):
                try:
                    old_emp = Employee.objects.only("user_id").get(pk=old_employee_id)
                    old_user = getattr(old_emp, "user", None)
                except Exception:
                    old_user = None
                if old_user:
                    revoke_access(obj, user=old_user, only=["view"])
    except Exception:
        # ACL must never break save paths
        pass

    # (2) HR Managers groups -> full access
    try:
        from django.contrib.auth.models import Group, Permission

        perm = Permission.objects.get(content_type__app_label="hr", codename="manage_all_hr")
        hr_groups = Group.objects.filter(permissions=perm)
        for g in hr_groups:
            grant_access(
                obj,
                group=g,
                view=True, change=True, delete=True,
                approve=True, assign=True, share=True,
            )
    except Exception:
        pass

    # (3) Employee itself -> view + change
    if getattr(getattr(obj, "_meta", None), "app_label", "") == "hr" and \
       getattr(getattr(obj, "_meta", None), "model_name", "") == "employee" and \
       getattr(obj, "user_id", None):
        grant_access(obj, user=obj.user, view=True, change=True)

    # (4) Assets-specific
    try:
        Asset = apps.get_model("assets", "Asset")
        AssetAssignment = apps.get_model("assets", "AssetAssignment")
    except Exception:
        Asset = None
        AssetAssignment = None

    if Asset is not None and isinstance(obj, Asset):
        holder = getattr(obj, "holder", None)
        holder_user = getattr(holder, "user", None) if holder else None
        if holder_user:
            grant_access(obj, user=holder_user, view=True, change=True)

    if AssetAssignment is not None and isinstance(obj, AssetAssignment):
        emp = getattr(obj, "employee", None)
        emp_user = getattr(emp, "user", None) if emp else None
        if emp_user:
            grant_access(obj, user=emp_user, view=True)
            asset = getattr(obj, "asset", None)
            if asset:
                grant_access(asset, user=emp_user, view=True, change=True)

    # (5) Performance-specific
    try:
        Evaluation = apps.get_model("performance", "Evaluation")
    except Exception:
        Evaluation = None

    if Evaluation is not None and isinstance(obj, Evaluation):
        emp = getattr(obj, "employee", None)
        emp_user = getattr(emp, "user", None) if emp else None
        if emp_user:
            grant_access(obj, user=emp_user, view=True)

    # (6) Department hierarchy managers -> operational rights
    base_dept = _get_base_department_for_obj(obj)
    if not base_dept:
        return

    seen_users = set()
    cur = base_dept
    while cur:
        mgr = getattr(cur, "manager", None)
        mgr_user = getattr(mgr, "user", None) if mgr else None
        if mgr_user and mgr_user.pk not in seen_users:
            grant_access(obj, user=mgr_user, view=True, change=True, approve=True, assign=True)
            seen_users.add(mgr_user.pk)
        cur = cur.parent

    # (7) Manager of this department -> view-only on parents
    try:
        base_mgr = getattr(base_dept, "manager", None)
        base_mgr_user = getattr(base_mgr, "user", None) if base_mgr else None
        if base_mgr_user:
            parent = base_dept.parent
            while parent:
                grant_access(
                    parent,
                    user=base_mgr_user,
                    view=True,
                    change=False, approve=False, assign=False, share=False,
                )
                parent = parent.parent
    except Exception:
        pass

    # (8) Department objects -> sibling managers view-only
    if getattr(getattr(obj, "_meta", None), "app_label", "") == "hr" and \
       getattr(getattr(obj, "_meta", None), "model_name", "") == "department":
        parent = getattr(obj, "parent", None)
        if parent:
            try:
                siblings = parent.children.exclude(pk=obj.pk)
                for s in siblings:
                    m = getattr(s, "manager", None)
                    mu = getattr(m, "user", None) if m else None
                    if mu:
                        grant_access(obj, user=mu, view=True, change=False)
            except Exception:
                pass


# ======================================================================================
# TEAM VISIBILITY (incremental rebuild)
# ======================================================================================

TEAM_EXTRA_FLAG = "team_visibility"


def _team_members_queryset(*, manager_id: int, company_id: Optional[int] = None):
    """
    Active employees with users reporting to manager_id (optional company scope).
    """
    _, Employee = _hr_models()
    qs = Employee.objects.filter(
        active=True,
        user__isnull=False,
        manager_id=manager_id,
    ).select_related("user").only("id", "user_id", "manager_id", "company_id", "active")
    if company_id is not None:
        qs = qs.filter(company_id=company_id)
    return qs


def rebuild_team_visibility_for_manager(*, manager_id: int, company_id: Optional[int] = None):
    """
    Incrementally rebuild team_visibility ACEs for ONE manager's team only.

    Guarantees:
    - Removes old team_visibility ACEs relevant to this manager/team.
    - Rebuilds:
        (A) members -> view manager
        (B) members -> view peers (same manager)
    """
    Department, Employee = _hr_models()
    ct = _employee_ct()

    team = list(_team_members_queryset(manager_id=manager_id, company_id=company_id))
    if not team:
        # Still need cleanup: clear any leftover ACEs among this manager + potential old members.
        # Minimal safe cleanup: delete ACEs on manager object with team_visibility for any user.
        ObjectACL.objects.filter(
            content_type=ct,
            object_id=manager_id,
            extra_perms__contains=[TEAM_EXTRA_FLAG],
        ).delete()
        return

    user_ids = [e.user_id for e in team if e.user_id]
    obj_ids = [manager_id] + [e.id for e in team]

    # 1) Delete only the affected ACEs (scoped by object_ids + user_ids + extra flag)
    ObjectACL.objects.filter(
        content_type=ct,
        object_id__in=obj_ids,
        user_id__in=user_ids,
        extra_perms__contains=[TEAM_EXTRA_FLAG],
    ).delete()

    # 2) Manager record (must be active + has user to be visible as "manager")
    try:
        manager_emp = Employee.objects.only("id", "user_id", "active", "company_id").get(pk=manager_id, active=True)
    except Employee.DoesNotExist:
        manager_emp = None

    # (A) Members -> view manager
    if manager_emp is not None:
        for emp in team:
            grant_access(
                manager_emp,
                user=emp.user,
                view=True,
                extras=[TEAM_EXTRA_FLAG],
            )

    # (B) Members -> view peers
    for emp in team:
        for peer in team:
            if peer.id == emp.id:
                continue
            grant_access(
                peer,
                user=emp.user,
                view=True,
                extras=[TEAM_EXTRA_FLAG],
            )


def rebuild_team_visibility_for_employee_change(
    *,
    old_manager_id: Optional[int],
    new_manager_id: Optional[int],
    old_company_id: Optional[int],
    new_company_id: Optional[int],
):
    """
    Rebuild only the affected teams:
      - old manager team (cleanup + rebuild)
      - new manager team (cleanup + rebuild)
    """
    if old_manager_id:
        rebuild_team_visibility_for_manager(manager_id=old_manager_id, company_id=old_company_id)
    if new_manager_id and new_manager_id != old_manager_id:
        rebuild_team_visibility_for_manager(manager_id=new_manager_id, company_id=new_company_id)


@receiver(pre_save, sender=_hr_models()[1])
def _employee_capture_team_fields(sender, instance, **kwargs):
    """
    Capture fields that affect team visibility ACL:
      - manager_id: membership changes
      - company_id: scope changes (if you scope by company)
      - active: membership changes
      - user_id: principal changes (who receives ACL)
    """
    if not instance.pk:
        instance._old_team_acl = None
        return

    try:
        old = sender.objects.only("manager_id", "company_id", "active", "user_id").get(pk=instance.pk)
        instance._old_team_acl = (old.manager_id, old.company_id, old.active, old.user_id)
    except sender.DoesNotExist:
        instance._old_team_acl = None


@receiver(post_save, sender=_hr_models()[1])
def _sync_team_visibility_on_employee_save(sender, instance, **kwargs):
    """
    Incremental rebuild ONLY if relevant fields changed.
    """
    old = getattr(instance, "_old_team_acl", None)
    new = (instance.manager_id, instance.company_id, instance.active, instance.user_id)

    if old != new:
        old_manager_id, old_company_id, _, _ = old or (None, None, None, None)
        rebuild_team_visibility_for_employee_change(
            old_manager_id=old_manager_id,
            new_manager_id=instance.manager_id,
            old_company_id=old_company_id,
            new_company_id=instance.company_id,
        )
