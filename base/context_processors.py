# base/context_processors.py
# يوفر current_company وallowed_companies لكل القوالب.


from django.contrib.auth import get_user_model
from .company_context import get_company_id, get_allowed_company_ids

User = get_user_model()

def company(request):
    from .models import Company
    cid = get_company_id()
    allowed = get_allowed_company_ids()
    current = Company.objects.filter(id=cid).first() if cid else None
    companies = Company.objects.filter(id__in=allowed)
    return {"current_company": current, "allowed_companies": companies}
