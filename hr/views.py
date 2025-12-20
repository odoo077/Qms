# hr/views.py
"""
HR Views (Odoo-like behavior)

Design principles:
- Company scope is enforced via CompanyOwnedMixin / CompanyScopeManager
- ACL is enforced via AccessControlledMixin + ACLManager
- No implicit magic or hidden permissions
- Views are thin: logic lives in models/forms
"""

from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import PermissionDenied
from django.urls import reverse_lazy
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
)

from base.acl_service import has_perm
from base.views import (
    BaseScopedListView,
    BaseScopedCreateView,
    BaseScopedUpdateView,
    BaseScopedDetailView,
)

from .models import Department, Job, Employee
from .forms import DepartmentForm, JobForm, EmployeeForm


# ==========================================================
# Departments
# ==========================================================

class DepartmentListView(LoginRequiredMixin, BaseScopedListView):
    """
    List departments for current company.

    - Company scoped
    - ACL: view
    """
    model = Department
    template_name = "hr/department_list.html"
    paginate_by = 50

    def get_queryset(self):
        qs = super().get_queryset()
        qs = qs.select_related("company", "parent", "manager").order_by("complete_name")
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_add"] = self.request.user.has_perm("hr.add_department")
        return ctx


class DepartmentDetailView(LoginRequiredMixin, DetailView):
    """
    Department Detail View (Odoo-like behavior)

    Rules:
    - Company scoped via CompanyScopeManager
    - NO object-level ACL
    - Edit permission via Django permissions only
    """

    model = Department
    template_name = "hr/department_detail.html"

    def get_queryset(self):
        """
        Company scope is applied automatically via CompanyScopeManager.
        """
        return (
            Department.objects
            .select_related("company", "parent", "manager")
            .prefetch_related("children")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user

        # --------------------------------------------------
        # Edit permission (Odoo-like)
        # --------------------------------------------------
        ctx["can_edit"] = (
            user.is_superuser
            or user.has_perm("hr.change_department")
        )

        return ctx

class DepartmentCreateView(LoginRequiredMixin, PermissionRequiredMixin, BaseScopedCreateView):
    """
    Create new department.

    - Permission: hr.add_department
    - Company is injected by BaseScopedCreateView
    """
    model = Department
    form_class = DepartmentForm
    template_name = "hr/department_form.html"
    success_url = reverse_lazy("hr:department_list")
    permission_required = "hr.add_department"


class DepartmentUpdateView(
    LoginRequiredMixin,
    PermissionRequiredMixin,
    BaseScopedUpdateView,
):
    """
    Department Update View (Odoo-like)

    Characteristics:
    - Company scoped (via BaseScopedUpdateView)
    - Permission-based (NOT ACL-based)
    - Superuser allowed implicitly
    - No record-level ACL for departments
    """

    model = Department
    form_class = DepartmentForm
    template_name = "hr/department_form.html"
    success_url = reverse_lazy("hr:department_list")

    # Django permission (not ACL)
    permission_required = "hr.change_department"
    raise_exception = True  # return 403 instead of redirect

    def get_queryset(self):
        """
        Departments are organization structure entities.

        Rules:
        - Scoped by company (handled by BaseScopedUpdateView)
        - NOT filtered by ACL
        """
        return (
            super()
            .get_queryset()
            .select_related("company", "parent", "manager")
        )

# ==========================================================
# Jobs
# ==========================================================

class JobListView(LoginRequiredMixin, BaseScopedListView):
    """
    List jobs for current company.
    """
    model = Job
    template_name = "hr/job_list.html"
    paginate_by = 50

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.select_related("company", "department").order_by("name")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_add"] = self.request.user.has_perm("hr.add_job")
        return ctx


class JobDetailView(LoginRequiredMixin, BaseScopedDetailView):
    """
    Job details.
    """
    model = Job
    template_name = "hr/job_detail.html"

    def get_queryset(self):
        return super().get_queryset().select_related("company", "department")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        obj = ctx.get("object")
        ctx["can_edit"] = bool(obj and has_perm(self.request.user, obj, "change"))
        return ctx


class JobCreateView(LoginRequiredMixin, PermissionRequiredMixin, BaseScopedCreateView):
    """
    Create new job.
    """
    model = Job
    form_class = JobForm
    template_name = "hr/job_form.html"
    success_url = reverse_lazy("hr:job_list")
    permission_required = "hr.add_job"


class JobUpdateView(LoginRequiredMixin, BaseScopedUpdateView):
    """
    Update job.
    """
    model = Job
    form_class = JobForm
    template_name = "hr/job_form.html"
    success_url = reverse_lazy("hr:job_list")

    def get_queryset(self):
        return Job.acl_objects.with_acl("change").select_related(
            "company", "department"
        )


# ==========================================================
# Employees
# ==========================================================

class EmployeeListView(LoginRequiredMixin, BaseScopedListView):
    """
    List employees for current company.

    - ACL: view
    """
    model = Employee
    template_name = "hr/employee_list.html"
    paginate_by = 50

    def get_queryset(self):
        qs = super().get_queryset()
        qs = qs.select_related(
            "company",
            "department",
            "job",
            "manager",
            "user",
        ).prefetch_related("categories")
        return qs.order_by("name")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_add"] = self.request.user.has_perm("hr.add_employee")
        return ctx


class EmployeeDetailView(LoginRequiredMixin, BaseScopedDetailView):
    """
    Employee profile (Odoo-like).

    - ACL: view
    - Company scoped
    """
    model = Employee
    template_name = "hr/employee_detail.html"

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related(
                "company",
                "department",
                "job",
                "manager",
                "coach",
                "user",
                "work_location",
                "work_contact",
            )
            .prefetch_related("categories")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        obj = ctx.get("object")

        ctx["can_edit"] = bool(obj and has_perm(self.request.user, obj, "change"))
        ctx["can_view_private"] = bool(
            obj and self.request.user.has_perm("hr.view_private_fields")
        )
        return ctx


class EmployeeCreateView(LoginRequiredMixin, PermissionRequiredMixin, BaseScopedCreateView):
    """
    Create employee.

    - Permission: hr.add_employee
    - Company injected automatically
    """
    model = Employee
    form_class = EmployeeForm
    template_name = "hr/employee_form.html"
    success_url = reverse_lazy("hr:employee_list")
    permission_required = "hr.add_employee"


class EmployeeUpdateView(LoginRequiredMixin, BaseScopedUpdateView):
    """
    Update employee.

    - ACL: change
    - Company scoped
    """
    model = Employee
    form_class = EmployeeForm
    template_name = "hr/employee_form.html"
    success_url = reverse_lazy("hr:employee_list")

    def get_queryset(self):
        return Employee.acl_objects.with_acl("change").select_related(
            "company",
            "department",
            "job",
            "manager",
            "coach",
            "user",
            "work_location",
        )
