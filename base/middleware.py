# base/middleware.py
from __future__ import annotations
from .security_context import set_current_user_id
from .company_context import (
    bootstrap_from_request,
    get_company_id,
    get_allowed_company_ids,
    clear_company,
)

class MultiCompanyMiddleware:
    """
    يفعّل سياق الشركة (active + allowed) لكل طلب، ويحقنه على request.*،
    ثم يمسحه بعد إرجاع الاستجابة لضمان عدم تسرّب السياق بين الطلبات.
    يجب وضعه بعد AuthenticationMiddleware.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        bootstrap_from_request(request)
        request.company_id = get_company_id(request)
        request.allowed_company_ids = get_allowed_company_ids(request)

        # ✅ مهم: ثبت المستخدم الحالي في السياق
        # بهذه الخطوة صار عندنا company + user في السياق، نستخدمهما لاحقًا في كويريات الـ ACL.
        set_current_user_id(getattr(request.user, "id", None))
        try:
            response = self.get_response(request)
        finally:
            clear_company()
            set_current_user_id(None)
        return response
