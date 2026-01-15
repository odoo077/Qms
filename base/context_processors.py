# base/context_processors.py

from base.company_context import (
    get_company_id,
    get_allowed_company_ids,
)
from base.models import Company


def company(request):
    """
    Inject company-related context into templates.

    This context processor:
    - Does NOT compute company logic
    - Relies fully on company_context as source of truth
    - Is optimized to minimize database queries
    """

    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {}

    # -------------------------------------------------
    # Allowed companies (for switcher UI)
    # -------------------------------------------------
    if user.is_superuser:
        allowed_companies = Company.objects.all()
    else:
        # QuerySet محفوظ، ولا يتم تقييمه إلا عند الاستعمال في template
        allowed_companies = user.companies.all()

    # 🔒 إخفاء الشركات غير النشطة من الـ UI (Company Switcher)
    if hasattr(Company, "active"):
        allowed_companies = allowed_companies.filter(active=True)

    # -------------------------------------------------
    # Active company IDs (ContextVar authoritative)
    # -------------------------------------------------
    active_ids = get_allowed_company_ids(request)

    # -------------------------------------------------
    # Current company (single object)
    # -------------------------------------------------
    current_company_id = get_company_id(request)
    current_company = None

    if current_company_id:
        # استعلام واحد مباشر بدل filter على QuerySet
        current_company = (
            Company.objects.filter(id=current_company_id).first()
        )

    # Fallback نظري فقط (لا يُفترض الوصول إليه)
    if not current_company:
        current_company = allowed_companies.first()

    return {
        # كل الشركات المسموح بها (للقائمة / السويتشر)
        "allowed_companies": allowed_companies,

        # IDs الشركات المفعّلة حاليًا (checkboxes)
        "active_ids": active_ids,

        # الشركة الحالية فقط
        "current_company": current_company,
    }
