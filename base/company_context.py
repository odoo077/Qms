from __future__ import annotations

from typing import Optional, Iterable, Tuple, List
from contextvars import ContextVar
from django.contrib.auth.models import AnonymousUser

# ===============================================================
# Context Variables (Request-safe / Thread-safe)
# ===============================================================

_current_company_id: ContextVar[Optional[int]] = ContextVar(
    "current_company_id", default=None
)

_allowed_company_ids: ContextVar[Tuple[int, ...]] = ContextVar(
    "allowed_company_ids", default=()
)

# ===============================================================
# Context Management
# ===============================================================

def set_company(company_id: Optional[int], allowed_ids: Iterable[int] = ()) -> None:
    """
    Set current company context for the active request.
    """
    _current_company_id.set(company_id)
    _allowed_company_ids.set(tuple(allowed_ids or ()))


def clear_company() -> None:
    """
    Clear company context at the end of the request.
    """
    _current_company_id.set(None)
    _allowed_company_ids.set(tuple())


def get_company_id(request=None) -> Optional[int]:
    """
    Return current company ID.
    Prefer request-bound value, fallback to ContextVar.
    """
    if request and hasattr(request, "company_id"):
        return request.company_id
    return _current_company_id.get()


def get_allowed_company_ids(request=None) -> List[int]:
    """
    Return active (selected) company IDs.

    Source of truth:
    - ContextVar (_allowed_company_ids) set by bootstrap_from_request()

    Session is persistence only, never authority.
    """

    # 1) Request-bound (set by middleware)
    if request and hasattr(request, "allowed_company_ids"):
        return list(request.allowed_company_ids or [])

    # 2) ContextVar (authoritative)
    ids = _allowed_company_ids.get()
    if ids:
        return list(ids)

    # 3) Very safe fallback (rare edge cases only)
    if request and getattr(request, "user", None) and request.user.is_authenticated:
        return list(
            request.user.companies.values_list("id", flat=True)
        )

    return []

# ===============================================================
# Internal Utilities
# ===============================================================

def _coerce_int(value) -> Optional[int]:
    """
    Safely coerce a value to int.
    """
    try:
        return int(value) if value is not None else None
    except Exception:
        return None


def resolve_default_company_id(
    user,
    allowed_ids: List[int],
    is_super: bool = False,
) -> Optional[int]:
    """
    Resolve the default company ID for the given user.

    Priority order (preserved exactly):
    1) UserSettings.default_company
    2) user.company
    3) First allowed company
    """

    # 1) UserSettings.default_company
    settings = getattr(user, "settings", None)
    if settings and getattr(settings, "default_company_id", None):
        cid = _coerce_int(settings.default_company_id)
        if cid and (is_super or cid in allowed_ids):
            return cid

    # 2) Explicit default company on user
    if getattr(user, "company_id", None):
        cid = _coerce_int(user.company_id)
        if cid and (is_super or cid in allowed_ids):
            return cid

    # 3) Fallback to first allowed company
    if allowed_ids:
        return allowed_ids[0]

    return None

# ===============================================================
# Main Bootstrap Logic (Single Source of Truth)
# ===============================================================

def bootstrap_from_request(request) -> None:
    """
    Initialize company context per request (Odoo-like behavior).

    Rules:
    - allowed companies = user.companies
    - current company priority:
        1) session['current_company_id']
        2) resolved default (settings → user.company → fallback)
    - active companies = session['active_company_ids'] ∩ allowed
    - current company must always be part of active companies
    """

    user = getattr(request, "user", AnonymousUser())
    allowed: List[int] = []
    current: Optional[int] = None
    is_super = bool(getattr(user, "is_superuser", False))

    if getattr(user, "is_authenticated", False):

        # 1) Allowed companies for user
        allowed = list(
            user.companies.values_list("id", flat=True)
        )

        # 2) Try current company from session
        sess_company_id = _coerce_int(
            request.session.get("current_company_id")
        )
        if sess_company_id and (is_super or sess_company_id in allowed):
            current = sess_company_id

        # 3) Resolve default company (single source of truth)
        if current is None:
            current = resolve_default_company_id(user, allowed, is_super)

        # 4) Sync current company to session
        if current and request.session.get("current_company_id") != current:
            request.session["current_company_id"] = current

        # 5) Resolve active companies from session
        session_active = request.session.get("active_company_ids", [])
        try:
            session_active = [int(cid) for cid in session_active]
        except Exception:
            session_active = []

        if not is_super:
            session_active = [cid for cid in session_active if cid in allowed]

        # If no active companies but current exists → activate current
        if not session_active and current:
            session_active = [current]

        # Ensure current is always active
        if current and current not in session_active:
            session_active.insert(0, current)

        # 6) Sync active companies to session
        if request.session.get("active_company_ids") != session_active:
            request.session["active_company_ids"] = session_active

        # 7) Finalize context
        set_company(current, session_active)

    else:
        set_company(None, ())

# ===============================================================
# Helper: Get Current Company Object (ContextVar-based)
# ===============================================================

from base.security_context import get_current_user_id


def get_current_company_object():
    """
    Return the current active Company object for the logged-in user.

    Uses ContextVar-based tracking.
    Safe for services, ACL, signals, etc.
    """
    user_id = get_current_user_id()
    if not user_id:
        return None

    company_id = get_company_id()
    if not company_id:
        return None

    # Local import to avoid circular dependency
    from base.models import Company

    try:
        return Company.objects.get(id=company_id)
    except Company.DoesNotExist:
        return None
