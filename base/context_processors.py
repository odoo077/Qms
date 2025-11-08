# base/context_processors.py
from base.company_context import get_company_id, get_allowed_company_ids
from base.models import Company

def company(request):
    if not request.user.is_authenticated:
        return {}

    # ✅ allowed_companies = كل الشركات المسموح بها للمستخدم (وليس النشطة فقط)
    if getattr(request.user, "is_superuser", False):
        allowed_companies_qs = Company.objects.all()
    else:
        allowed_companies_qs = request.user.companies.all()

    # ✅ active_ids = الشركات المفعّلة حاليًا (من الجلسة / السياق)
    active_ids = get_allowed_company_ids(request) or []

    # الشركة الحالية
    current_id = get_company_id(request) or request.user.company_id
    current_company = allowed_companies_qs.filter(id=current_id).first() or allowed_companies_qs.first()

    return {
        "allowed_companies": allowed_companies_qs,  # ← الآن تظهر كل المسموح بها
        "active_ids": list(active_ids),             # ← المفعّلة فقط (تُعلَّم بالـ checkbox)
        "current_company": current_company,
    }
