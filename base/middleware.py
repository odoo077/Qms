# base/middleware.py
from .company_context import bootstrap_from_request, get_company_id, get_allowed_company_ids

class MultiCompanyMiddleware:
    """
    يحقن الشركة النشطة والقائمة المسموحة في سياق التنفيذ وعلى request.*.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        bootstrap_from_request(request)
        request.company_id = get_company_id()
        request.allowed_company_ids = get_allowed_company_ids()
        return self.get_response(request)
