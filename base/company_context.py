# base/company_context.py
from __future__ import annotations
from typing import Optional, Iterable
from contextvars import ContextVar
from django.contrib.auth.models import AnonymousUser

_current_company_id: ContextVar[Optional[int]] = ContextVar("current_company_id", default=None)
_allowed_company_ids: ContextVar[Iterable[int]] = ContextVar("allowed_company_ids", default=())

def set_company(company_id: Optional[int], allowed_ids: Iterable[int] = ()):
    _current_company_id.set(company_id)
    _allowed_company_ids.set(tuple(allowed_ids or ()))

def get_company_id() -> Optional[int]:
    return _current_company_id.get()

def get_allowed_company_ids() -> tuple[int, ...]:
    return tuple(_allowed_company_ids.get() or ())

def bootstrap_from_request(request):
    user = getattr(request, "user", AnonymousUser())
    allowed = ()
    current = None
    if getattr(user, "is_authenticated", False):
        allowed = list(user.companies.values_list("id", flat=True))
        # الشركة النشطة من الجلسة أو الافتراضية للمستخدم
        current = request.session.get("current_company_id") or getattr(user, "company_id", None)
        if current and current not in allowed and not user.is_superuser:
            # لو الجلسة تحمل شركة غير مسموح بها – اسقطها
            current = None
        if not current and allowed:
            current = allowed[0]
    set_company(current, allowed)
