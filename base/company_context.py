from __future__ import annotations
from typing import Optional, Iterable, Tuple
from contextvars import ContextVar
from django.contrib.auth.models import AnonymousUser

# السياق الحالي (Company-in-Context) لطبقة ORM ومدير النطاق
_current_company_id: ContextVar[Optional[int]] = ContextVar("current_company_id", default=None)
_allowed_company_ids: ContextVar[Tuple[int, ...]] = ContextVar("allowed_company_ids", default=())

def set_company(company_id: Optional[int], allowed_ids: Iterable[int] = ()) -> None:
    """Set the active company and the allowed scope for the current context (request/thread)."""
    _current_company_id.set(company_id)
    _allowed_company_ids.set(tuple(allowed_ids or ()))

def get_company_id() -> Optional[int]:
    """Return the active company id for the current context."""
    return _current_company_id.get()

def get_allowed_company_ids() -> tuple[int, ...]:
    """Return the ids of allowed companies for the current context."""
    return tuple(_allowed_company_ids.get() or ())

def bootstrap_from_request(request) -> None:
    """
    تحديد الشركة النشطة والمدى المسموح به على طريقة Odoo:
      1) session["current_company_id"] إن كانت مسموح بها.
      2) UserSettings.default_company إن كانت مسموح بها.
      3) user.company إن كانت مسموح بها.
      4) أول شركة من المسموح بها (fallback).
    ملاحظة: لا نكسر تفضيل المستخدم مطلقًا، ونسمح للمشرف superuser بتجاوز التحقق.
    """
    user = getattr(request, "user", AnonymousUser())
    allowed: list[int] = []
    current: Optional[int] = None

    if getattr(user, "is_authenticated", False):
        # المدى المسموح للمستخدم
        allowed = list(user.companies.values_list("id", flat=True))

        # 1) من الجلسة
        current = request.session.get("current_company_id")

        # إن كانت الشركة من الجلسة غير مسموح بها (والمستخدم ليس superuser) تجاهلها
        if current and current not in allowed and not getattr(user, "is_superuser", False):
            current = None

        # 2) من UserSettings.default_company (تفضيل المستخدم)
        if not current and hasattr(user, "usersettings") and user.usersettings and user.usersettings.default_company_id:
            default_id = user.usersettings.default_company_id
            if default_id in allowed or getattr(user, "is_superuser", False):
                current = default_id

        # 3) من user.company (الشركة الافتراضية لحساب المستخدم)
        if not current and getattr(user, "company_id", None):
            if (user.company_id in allowed) or getattr(user, "is_superuser", False):
                current = user.company_id

        # 4) fallback: أول مسموح بها
        if not current and allowed:
            current = allowed[0]

    set_company(current, allowed)
