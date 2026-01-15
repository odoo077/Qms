from __future__ import annotations

from base.security_context import set_current_user_id
from base.company_context import (
    bootstrap_from_request,
    get_company_id,
    get_allowed_company_ids,
    clear_company,
)


class MultiCompanyMiddleware:
    """
    Initialize and manage company context per request.

    Responsibilities:
    - Bootstrap company context (ContextVar-based)
    - Inject read-only company attributes into request
    - Bind current user to security context (ACL usage)
    - Ensure context cleanup after response

    Must be placed AFTER AuthenticationMiddleware.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        # -------------------------------------------------
        # 1) Bootstrap company context (single source of truth)
        # -------------------------------------------------
        bootstrap_from_request(request)

        # -------------------------------------------------
        # 2) Inject context into request (read-only helpers)
        # -------------------------------------------------
        request.company_id = get_company_id()
        request.allowed_company_ids = get_allowed_company_ids()

        # -------------------------------------------------
        # 3) Bind current user to security context (ACL)
        # -------------------------------------------------
        set_current_user_id(
            getattr(request.user, "id", None)
        )

        try:
            response = self.get_response(request)
        finally:
            # -------------------------------------------------
            # 4) Cleanup context (prevent leakage)
            # -------------------------------------------------
            clear_company()
            set_current_user_id(None)

        return response
