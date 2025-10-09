# performance/views/base.py
from typing import Optional
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.db import models
from django.http import Http404
from django.utils.functional import cached_property

try:
    from guardian.shortcuts import get_objects_for_user
except Exception:  # guardian not installed or not ready
    get_objects_for_user = None


class LoginRequired(LoginRequiredMixin):
    """Require authentication for all views."""
    login_url = "login"
    redirect_field_name = "next"


class CompanyScopedQuerysetMixin:
    """
    Ensure queryset is filtered by the current company.
    Assumes models use CompanyScopeManager as default .objects.
    """
    company_fk_name: str = "company"  # override if needed

    def get_request_company_id(self) -> Optional[int]:
        # Adjust this to your actual user/company relation
        return getattr(getattr(self.request, "user", None), "company_id", None)

    def get_queryset(self):
        qs = super().get_queryset()
        company_id = self.get_request_company_id()
        if company_id and self.company_fk_name in [f.name for f in qs.model._meta.fields]:
            qs = qs.filter(**{f"{self.company_fk_name}_id": company_id})
        return qs


class UserStampedSaveMixin:
    """
    Auto-set created_by / updated_by and default company (if empty).
    This complements your signals; it’s safe and idempotent.
    """
    company_fk_name: str = "company"

    def get_request_company_id(self) -> Optional[int]:
        return getattr(getattr(self.request, "user", None), "company_id", None)

    def form_valid(self, form):
        obj = form.instance
        user = getattr(self.request, "user", None)
        # company default
        if hasattr(obj, f"{self.company_fk_name}_id") and not getattr(obj, f"{self.company_fk_name}_id"):
            cid = self.get_request_company_id()
            if cid:
                setattr(obj, f"{self.company_fk_name}_id", cid)
        # user-stamp
        if hasattr(obj, "created_by") and not obj.pk:
            setattr(obj, "created_by", user)
        if hasattr(obj, "updated_by"):
            setattr(obj, "updated_by", user)
        return super().form_valid(form)


class ObjectPermissionRequiredMixin(UserPassesTestMixin):
    """
    Enforce object-level permissions using django-guardian.
    - Set `object_permission_map` like:
        {"GET": ["performance.view_objective"], "POST": ["performance.change_objective"], ...}
      or set a single `required_perms` iterable to apply for all methods.
    - Override `get_permission_object()` to return the model instance.
    """
    required_perms = None  # e.g., ["performance.view_objective"]
    object_permission_map = None  # e.g., {"GET": [...], "POST": [...]}

    def get_permission_object(self):
        # Must be implemented by views that require object permissions
        raise NotImplementedError("get_permission_object() must return the object to check permissions on.")

    def test_func(self):
        user = self.request.user
        if not user or not user.is_authenticated:
            return False

        obj = self.get_permission_object()
        if obj is None:
            raise Http404("Object not found.")

        # Resolve required perms for HTTP method
        perms = None
        if self.object_permission_map:
            perms = self.object_permission_map.get(self.request.method, None)
        if perms is None:
            perms = self.required_perms or []

        # Check each perm
        for p in perms:
            if not user.has_perm(p, obj):
                return False
        return True

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied
        return super().handle_no_permission()
