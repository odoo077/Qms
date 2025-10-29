# base/company_context.py
from __future__ import annotations
from typing import Optional, Iterable, Tuple, List
from contextvars import ContextVar
from django.contrib.auth.models import AnonymousUser

# -------------------------------------------------
# Context Vars (فعّالة لكل request/thread)
# -------------------------------------------------
_current_company_id: ContextVar[Optional[int]] = ContextVar("current_company_id", default=None)
_allowed_company_ids: ContextVar[Tuple[int, ...]] = ContextVar("allowed_company_ids", default=())

def set_company(company_id: Optional[int], allowed_ids: Iterable[int] = ()) -> None:
    """اضبط الشركة النشطة والمدى المسموح به في السياق الحالي."""
    _current_company_id.set(company_id)
    _allowed_company_ids.set(tuple(allowed_ids or ()))

def clear_company() -> None:
    """امسح قيم السياق (للاستعمال في نهاية الطلب داخل الميدلوير)."""
    _current_company_id.set(None)
    _allowed_company_ids.set(tuple())

def get_company_id() -> Optional[int]:
    """أعد معرّف الشركة النشطة في هذا السياق."""
    return _current_company_id.get()

def get_allowed_company_ids() -> tuple[int, ...]:
    """أعد قائمة الشركات المسموح بها في هذا السياق."""
    return tuple(_allowed_company_ids.get() or ())

def _coerce_int(v) -> Optional[int]:
    try:
        return int(v) if v is not None else None
    except Exception:
        return None

def bootstrap_from_request(request) -> None:
    """
    تحديد الشركة النشطة والمدى المسموح به على طريقة Odoo (Priority):
      1) session["current_company_id"] إن كانت ضمن المسموح.
      2) UserSettings.default_company إن كانت ضمن المسموح.
      3) user.company إن كانت ضمن المسموح.
      4) أول شركة من المسموح بها (fallback).
    المشرف (superuser) يتجاوز تحقق "ضمن المسموح".
    """
    user = getattr(request, "user", AnonymousUser())
    allowed: List[int] = []
    current: Optional[int] = None
    is_super = bool(getattr(user, "is_superuser", False))

    if getattr(user, "is_authenticated", False):
        # 1) نطاق الشركات المسموح بها للمستخدم
        allowed = list(user.companies.values_list("id", flat=True))

        # 2) محاولة استخدام الشركة من الجلسة
        sess_val = request.session.get("current_company_id")
        sess_company_id = _coerce_int(sess_val)
        if sess_company_id and (is_super or sess_company_id in allowed):
            current = sess_company_id

        # 3) تفضيل المستخدم (UserSettings.default_company)
        settings = getattr(user, "settings", None)
        if current is None and settings and getattr(settings, "default_company_id", None):
            default_id = _coerce_int(settings.default_company_id)
            if default_id and (is_super or default_id in allowed):
                current = default_id

        # 4) الشركة المعينة على حساب المستخدم
        if current is None and getattr(user, "company_id", None):
            user_company_id = _coerce_int(user.company_id)
            if user_company_id and (is_super or user_company_id in allowed):
                current = user_company_id

        # 5) Fallback: أول شركة مسموح بها
        if current is None and allowed:
            current = allowed[0]

        # مزامنة الجلسة إذا تغيّرت
        if current and request.session.get("current_company_id") != current:
            request.session["current_company_id"] = current

    # اضبط السياق للاستخدام داخل ORM managers
    set_company(current, allowed)
