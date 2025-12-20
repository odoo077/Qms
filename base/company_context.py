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

def get_company_id(request=None):
    if request and hasattr(request, "company_id"):
        return request.company_id
    return _current_company_id.get()

def get_allowed_company_ids(request=None):
    """
    ارجع الشركات النشطة من الجلسة أو من user.companies إذا كانت الجلسة فارغة.
    """
    if request:
        ids = request.session.get("active_company_ids")
        if not ids:
            if getattr(request, "user", None) and request.user.is_authenticated:
                ids = list(request.user.companies.values_list("id", flat=True))
                # خزّنها في الجلسة ليستمر ظهورها بعد ذلك
                request.session["active_company_ids"] = ids
        return ids or []
    return list(_allowed_company_ids.get() or ())



def _coerce_int(v) -> Optional[int]:
    try:
        return int(v) if v is not None else None
    except Exception:
        return None

def bootstrap_from_request(request) -> None:
    """
    تحديد الشركة النشطة والمدى على طريقة Odoo:
      - الشركات الفعّالة (selected) = session['active_company_ids'] ∩ allowed
      - الشركة الحالية current يجب أن تنتمي للـ selected وإلا تُضاف/تُصحّح
    """
    user = getattr(request, "user", AnonymousUser())
    allowed: List[int] = []
    current: Optional[int] = None
    is_super = bool(getattr(user, "is_superuser", False))

    if getattr(user, "is_authenticated", False):
        # 1) الشركات المسموح بها للمستخدم
        allowed = list(user.companies.values_list("id", flat=True))

        # 2) حاول من الجلسة
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

        # 5) Fallback
        if current is None and allowed:
            current = allowed[0]

        # مزامنة current في الجلسة
        if current and request.session.get("current_company_id") != current:
            request.session["current_company_id"] = current

        # 6) الشركات النشطة من الجلسة (وقيّدها بالمسموح)
        session_active = request.session.get("active_company_ids", [])
        try:
            session_active = [int(x) for x in session_active]
        except Exception:
            session_active = []

        if not is_super:
            session_active = [cid for cid in session_active if cid in allowed]

        # إذا لا يوجد نشط لكن لدينا current → اجعل النشطة = [current]
        if not session_active and current:
            session_active = [current]

        # تأكد أن current ضمن النشطة
        if current and current not in session_active:
            session_active.insert(0, current)

        # مزامنة النشطة في الجلسة
        if request.session.get("active_company_ids") != session_active:
            request.session["active_company_ids"] = session_active

        # اضبط السياق بالقيم النهائية
        set_company(current, session_active)
    else:
        set_company(None, ())

# ===============================================================
# Helper: Get current company object (safe ContextVar version)
# ===============================================================
from base.security_context import get_current_user_id


def get_current_company_object():
    """
    Returns the current active Company object for the logged-in user,
    using ContextVar-based user tracking.
    Avoids circular import with base.models.
    """
    user_id = get_current_user_id()
    if not user_id:
        return None

    # ⬇️ import المحلي داخل الدالة لمنع الدوران
    from django.contrib.auth import get_user_model
    from base import models as base_models

    User = get_user_model()
    user = User.objects.filter(id=user_id).first()
    if not user:
        return None

    company_id = get_company_id()
    if not company_id:
        return None

    try:
        return base_models.Company.objects.get(id=company_id)
    except base_models.Company.DoesNotExist:
        return None
