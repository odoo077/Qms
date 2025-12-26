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
    UpdateView, TemplateView,
)

from base.acl_service import has_perm
from base.company_context import get_allowed_company_ids, get_company_id
from base.models import Company
from base.views import (
    BaseScopedListView,
    BaseScopedCreateView,
    BaseScopedUpdateView,
    BaseScopedDetailView,
)

from .models import Department, Job, Employee, get_root_departments, build_department_tree
from .forms import DepartmentForm, JobForm, EmployeeForm


# ==========================================================
# Departments
# ==========================================================

class DepartmentListView(LoginRequiredMixin, TemplateView):
    """
    Department Tree View (Odoo-like)

    Characteristics:
    - No flat queryset
    - Tree is built in backend
    - Multi-company aware
    - One tree per company (best practice)
    """

    template_name = "hr/department_list.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        # الشركات المسموح بها حسب السياق (Multi-Company)
        allowed_company_ids = get_allowed_company_ids(self.request)

        departments_by_company = {}

        for company in Company.objects.filter(id__in=allowed_company_ids):
            roots = get_root_departments(company.id)
            departments_by_company[company] = build_department_tree(roots, depth=0)

        ctx["departments_by_company"] = departments_by_company

        # صلاحية الإضافة
        ctx["can_add"] = self.request.user.has_perm("hr.add_department")

        return ctx

class DepartmentDetailView(LoginRequiredMixin, BaseScopedDetailView):
    """
    Department Detail View (Odoo-like behavior)

    Rules:
    - Company scoped via BaseScopedDetailView (consistent with the app)
    - Edit permission via Django permissions only
    """

    model = Department
    template_name = "hr/department_detail.html"

    def get_object(self, queryset=None):
        """
        Department is a structural object:
        - No object-level ACL
        - Company scope only
        - Django permission controls edit, not view
        """
        obj = super(BaseScopedDetailView, self).get_object(queryset=queryset)

        # تحقق نطاق الشركة فقط
        active_ids = get_allowed_company_ids(self.request)
        if active_ids and obj.company_id not in active_ids:
            raise PermissionDenied("Department is outside active company scope.")

        return obj

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related("company", "parent", "manager")
            .prefetch_related("children")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # -------------------------------
        # Sub-departments (children)
        # -------------------------------
        ctx["children"] = (
            self.object.children
            .select_related("company", "manager")
            .order_by("name")
        )

        # -------------------------------
        # Employees in this department
        # -------------------------------
        from hr.models import Employee

        ctx["employees"] = (
            Employee.objects
            .filter(department=self.object)
            .select_related("company", "job", "manager", "user")
            .order_by("name")
        )
        user = self.request.user

        ctx["can_edit"] = (
            user.is_superuser
            or user.has_perm("hr.change_department")
        )
        return ctx

class DepartmentCreateView(
    LoginRequiredMixin,
    PermissionRequiredMixin,
    BaseScopedCreateView,
):
    """
    Create Department (STRUCTURAL):
    - Django permission only (hr.add_department)
    - Company set from active context (never from POST)
    """
    model = Department
    form_class = DepartmentForm
    template_name = "hr/department_form.html"
    success_url = reverse_lazy("hr:department_list")
    permission_required = "hr.add_department"

    def form_valid(self, form):
        # enforce company from active context (single source of truth)
        cid = get_company_id(self.request)
        if not cid:
            raise PermissionDenied("No active company selected.")

        allowed = get_allowed_company_ids(self.request)
        if allowed and cid not in allowed:
            raise PermissionDenied("Company is outside active scope.")

        form.instance.company_id = cid

        # IMPORTANT: call BaseScopedCreateView for its company-scope checks
        return super().form_valid(form)


class DepartmentUpdateView(
    LoginRequiredMixin,
    PermissionRequiredMixin,
    BaseScopedUpdateView,
):
    """
    Update Department (STRUCTURAL):
    - NO record-level ACL
    - Company scope only
    - Django permission: hr.change_department
    """
    model = Department
    form_class = DepartmentForm
    template_name = "hr/department_form.html"
    success_url = reverse_lazy("hr:department_list")

    permission_required = "hr.change_department"
    raise_exception = True

    def get_queryset(self):
        # company scoping handled in _enforce_object_scope_or_404 (below)
        return Department.objects.select_related("company", "parent", "manager")

    def _enforce_object_scope_or_404(self, obj):
        allowed_company_ids = get_allowed_company_ids(self.request)
        if allowed_company_ids and obj.company_id not in allowed_company_ids:
            raise PermissionDenied("Department is outside active company scope.")
        return obj

    def form_valid(self, form):
        # Enforce company from the existing object
        form.instance.company_id = self.object.company_id

        # Ensure missing hidden color never blocks save
        if getattr(form.instance, "color", None) is None:
            form.instance.color = self.object.color or 0

        # 🔴 critical: bypass BaseScopedUpdateView.form_valid (it enforces record ACL)
        return UpdateView.form_valid(self, form)

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
