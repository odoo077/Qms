# hr/views.py
"""
HR Views (Odoo-like behavior)

Design principles:
- Company scope is enforced via CompanyOwnedMixin / CompanyScopeManager
- ACL is enforced via AccessControlledMixin + ACLManager
- No implicit magic or hidden permissions
- Views are thin: logic lives in models/forms
"""
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST
from django.contrib import messages
from base.company_context import get_company_id, set_company
from base.models import Company
from .models import Department, Job, Employee, get_root_departments, build_department_tree
from .forms import DepartmentForm, JobForm, EmployeeForm
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q, F, Value
from django.db.models.functions import Coalesce, Greatest
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.views.generic import TemplateView
from django.views.generic.edit import UpdateView
from django.views import View
from base.company_context import get_allowed_company_ids
from base.acl_service import has_perm
from base.views import BaseScopedListView, BaseScopedDetailView, BaseScopedCreateView, BaseScopedUpdateView
from skills.models import EmployeeSkill

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
    - Company selectable
    - Default = active company (or first allowed)
    """
    model = Department
    form_class = DepartmentForm
    template_name = "hr/department_form.html"
    success_url = reverse_lazy("hr:department_list")
    permission_required = "hr.add_department"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        allowed = get_allowed_company_ids(self.request) or []
        active_cid = get_company_id(self.request) or (allowed[0] if allowed else None)

        kwargs["request"] = self.request
        kwargs["allowed_company_ids"] = allowed
        kwargs["active_company_id"] = active_cid

        if active_cid:
            kwargs.setdefault("initial", {})
            kwargs["initial"]["company"] = active_cid

        return kwargs

    def form_valid(self, form):
        allowed = get_allowed_company_ids(self.request) or []
        active_cid = get_company_id(self.request) or (allowed[0] if allowed else None)

        # ensure company exists
        company = form.cleaned_data.get("company")
        if not company and active_cid:
            company = Company.objects.filter(pk=active_cid).first()

        if not company:
            raise PermissionDenied("No active company selected.")

        # enforce scope
        if allowed and company.id not in allowed:
            raise PermissionDenied("Company is outside active scope.")

        form.instance.company = company

        # protect parent/company mismatch early (before model.clean message confusion)
        if form.instance.parent_id and form.instance.parent.company_id != form.instance.company_id:
            form.add_error("parent", "Parent department must belong to the same company.")
            return self.form_invalid(form)

        return super().form_valid(form)


class DepartmentUpdateView(
    LoginRequiredMixin,
    PermissionRequiredMixin,
    BaseScopedUpdateView,
):
    """
    Update Department (STRUCTURAL):
    - Company scope only (NO record-level ACL)
    - Company locked to object
    """
    model = Department
    form_class = DepartmentForm
    template_name = "hr/department_form.html"
    success_url = reverse_lazy("hr:department_list")

    permission_required = "hr.change_department"
    raise_exception = True

    def get_queryset(self):
        return Department.objects.select_related("company", "parent", "manager")

    def _enforce_object_scope_or_404(self, obj):
        allowed_company_ids = get_allowed_company_ids(self.request) or []
        if allowed_company_ids and obj.company_id not in allowed_company_ids:
            raise PermissionDenied("Department is outside active company scope.")
        return obj

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        allowed = get_allowed_company_ids(self.request) or []
        kwargs["request"] = self.request
        kwargs["allowed_company_ids"] = allowed
        kwargs["active_company_id"] = self.object.company_id
        return kwargs

    def form_valid(self, form):
        form.instance.company_id = self.object.company_id

        if getattr(form.instance, "color", None) is None:
            form.instance.color = self.object.color or 0

        if form.instance.parent_id and form.instance.parent.company_id != form.instance.company_id:
            form.add_error("parent", "Parent department must belong to the same company.")
            return self.form_invalid(form)

        return UpdateView.form_valid(self, form)

# ==========================================================
# Jobs
# ==========================================================


class JobListView(LoginRequiredMixin, BaseScopedListView):
    """
    List jobs for allowed companies (multi-company aware).
    """
    model = Job
    template_name = "hr/job_list.html"
    paginate_by = 50

    def get_queryset(self):
        qs = super().get_queryset().select_related("company", "department")

        # stats (active employees per job)
        qs = qs.annotate(
            employees_count=Count("employee_set", filter=Q(employee_set__active=True), distinct=True),
        ).annotate(
            vacancies=Greatest(
                Value(0),
                Coalesce(F("no_of_recruitment"), Value(0)) - Coalesce(F("employees_count"), Value(0)),
            )
        ).order_by("name")

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_add"] = self.request.user.has_perm("hr.add_job")
        return ctx

class JobDetailView(LoginRequiredMixin, BaseScopedDetailView):
    """
    Job Detail (STRUCTURAL):
    - Company scope only
    - NO record-level ACL
    """
    model = Job
    template_name = "hr/job_detail.html"

    def get_queryset(self):
        return Job.objects.select_related(
            "company", "department"
        ).prefetch_related(
            "employee_set__department",
            "employee_set__manager",
        )


    def _enforce_object_scope_or_404(self, obj):
        allowed = get_allowed_company_ids(self.request)
        if allowed and obj.company_id not in allowed:
            raise PermissionDenied("Job is outside active company scope.")
        return obj

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        job = self.object

        ctx["employees"] = (
            job.employee_set
            .filter(active=True)
            .select_related("department", "manager")
            .order_by("name")
        )

        ctx["can_edit"] = self.request.user.has_perm("hr.change_job")
        ctx["can_manage_employees"] = self.request.user.has_perm(
            "hr.change_employee"
        )

        return ctx


class JobCreateView(LoginRequiredMixin, PermissionRequiredMixin, BaseScopedCreateView):
    """
    Create new job (company auto-default from allowed companies; user can change).
    """
    model = Job
    form_class = JobForm
    template_name = "hr/job_form.html"
    success_url = reverse_lazy("hr:job_list")
    permission_required = "hr.add_job"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        allowed_ids = get_allowed_company_ids(self.request)
        kwargs["allowed_company_ids"] = allowed_ids
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        allowed_ids = get_allowed_company_ids(self.request)
        if allowed_ids:
            initial.setdefault("company", allowed_ids[0])
        return initial


class JobUpdateView(
    LoginRequiredMixin,
    PermissionRequiredMixin,
    BaseScopedUpdateView,
):
    """
    Job Update (STRUCTURAL):
    - NO record-level ACL
    - Company scope only
    - Django permission only
    """
    model = Job
    form_class = JobForm
    template_name = "hr/job_form.html"
    success_url = reverse_lazy("hr:job_list")

    permission_required = "hr.change_job"
    raise_exception = True

    def get_queryset(self):
        return Job.objects.select_related("company", "department")

    def _enforce_object_scope_or_404(self, obj):
        """
        OVERRIDE:
        Disable record-level ACL.
        """
        allowed_company_ids = get_allowed_company_ids(self.request)
        if allowed_company_ids and obj.company_id not in allowed_company_ids:
            raise PermissionDenied("Job is outside active company scope.")
        return obj

    def form_valid(self, form):
        """
        Bypass BaseScopedUpdateView.form_valid()
        which enforces record ACL.
        """
        form.instance.company_id = self.object.company_id
        return UpdateView.form_valid(self, form)

class JobEmployeeUpdateView(
    LoginRequiredMixin,
    PermissionRequiredMixin,
    BaseScopedUpdateView,
):
    """
    Change employee job (Odoo-like, FINAL).
    - Company scope only
    - Django permission only (hr.change_employee)
    - NO record-level ACL
    """
    model = Employee
    fields = ("job",)
    template_name = "hr/job_employee_form.html"
    permission_required = "hr.change_employee"
    raise_exception = True
    success_url = reverse_lazy("hr:employee_list")

    def get_queryset(self):
        return Employee.objects.select_related(
            "company", "job", "department"
        )

    def _enforce_object_scope_or_404(self, obj):
        allowed = get_allowed_company_ids(self.request)
        if allowed and obj.company_id not in allowed:
            raise PermissionDenied("Employee outside company scope.")
        return obj

    def form_valid(self, form):
        # enforce company from existing object
        form.instance.company_id = self.object.company_id

        # job must belong to same company
        if form.instance.job and form.instance.job.company_id != form.instance.company_id:
            raise PermissionDenied("Job must belong to same company.")

        # bypass BaseScopedUpdateView.form_valid (ACL per-record)
        return UpdateView.form_valid(self, form)



# ==========================================================
# HTMX / Ajax
# ==========================================================

class AjaxDepartmentOptionsView(LoginRequiredMixin, View):
    """
    Return <option> list for Department select filtered by company.
    Used by JobForm (company -> department cascading).
    """
    template_name = "hr/partials/department_options.html"

    def get(self, request, *args, **kwargs):
        allowed_ids = get_allowed_company_ids(request)
        company_id = request.GET.get("company_id")

        try:
            company_id = int(company_id) if company_id else None
        except ValueError:
            company_id = None

        if not company_id or (allowed_ids and company_id not in allowed_ids):
            # return empty list but keep placeholder
            html = render_to_string(self.template_name, {"departments": []}, request=request)
            return HttpResponse(html)

        departments = (
            Department.objects
            .filter(company_id=company_id, active=True)
            .only("id", "name", "complete_name")
            .order_by("complete_name")
        )
        html = render_to_string(self.template_name, {"departments": departments}, request=request)
        return HttpResponse(html)

# ==========================================================
# Employees
# ==========================================================

class EmployeeListView(LoginRequiredMixin, BaseScopedListView):
    model = Employee
    template_name = "hr/employee_list.html"
    paginate_by = 50
    context_object_name = "employees"

    def get_queryset(self):
        qs = (
            super()
            .get_queryset()
            .select_related("company", "department", "job", "manager", "user")
        )

        q = (self.request.GET.get("q") or "").strip()
        if q:
            qs = qs.filter(name__icontains=q)

        return qs.order_by("name")

class EmployeeDetailView(LoginRequiredMixin, BaseScopedDetailView):
    """
    Employee detail view (Odoo-like)

    - Company scoped
    - No ACL enforcement for now (as requested)
    - Includes Employee Skills tab
    """

    model = Employee
    template_name = "hr/employee_detail.html"
    context_object_name = "employee"

    # --------------------------------------------------
    # Scope enforcement (Company only)
    # --------------------------------------------------
    def _enforce_object_scope_or_404(self, obj):
        allowed_company_ids = get_allowed_company_ids(self.request)
        if allowed_company_ids and obj.company_id not in allowed_company_ids:
            raise PermissionDenied("Employee is outside active company scope.")
        return obj

    # --------------------------------------------------
    # Optimized queryset
    # --------------------------------------------------
    def get_queryset(self):
        return (
            Employee.objects
            .select_related(
                "company",
                "department",
                "job",
                "manager",
                "coach",
                "user",
                "work_location",
            )
            .prefetch_related(
                "categories",
                "managed_employees",
            )
        )

    # --------------------------------------------------
    # Context
    # --------------------------------------------------
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        employee = self.object

        # -------- UI flags (no permissions for now)
        ctx["can_edit"] = True

        # -------- Management chain
        chain = []
        node = employee.manager
        while node:
            chain.append(node)
            node = node.manager
        ctx["manager_chain"] = chain

        # -------- Subordinates
        ctx["subordinates"] = employee.managed_employees.filter(active=True)

        # -------- Employee Skills (IMPORTANT PART)
        ctx["employee_skills"] = (
            EmployeeSkill.objects
            .filter(employee=employee)
            .select_related(
                "skill_type",
                "skill",
                "skill_level",
            )
            .order_by("skill_type__name", "skill__name")
        )

        return ctx

class EmployeeCreateView(LoginRequiredMixin, BaseScopedCreateView):
    model = Employee
    form_class = EmployeeForm
    template_name = "hr/employee_form.html"
    success_url = reverse_lazy("hr:employee_list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        allowed = get_allowed_company_ids(self.request) or []
        kwargs["request"] = self.request
        kwargs["allowed_company_ids"] = allowed
        kwargs["active_company_id"] = get_company_id(self.request)
        return kwargs

class EmployeeUpdateView(LoginRequiredMixin, BaseScopedUpdateView):
    model = Employee
    form_class = EmployeeForm
    template_name = "hr/employee_form.html"
    success_url = reverse_lazy("hr:employee_list")

    def get_queryset(self):
        return Employee.objects.select_related(
            "company",
            "department",
            "job",
            "manager",
            "coach",
            "user",
        )

    def _enforce_object_scope_or_404(self, obj):
        allowed = get_allowed_company_ids(self.request)
        if allowed and obj.company_id not in allowed:
            raise PermissionDenied("Employee outside company scope.")
        return obj

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        kwargs["allowed_company_ids"] = get_allowed_company_ids(self.request)
        kwargs["active_company_id"] = self.object.company_id
        return kwargs

@method_decorator(require_POST, name="dispatch")
class EmployeeBulkActionView(LoginRequiredMixin, View):
    def post(self, request):
        action = request.POST.get("action")
        ids = request.POST.getlist("ids")

        if not ids:
            messages.warning(request, "No employees selected.")
            return redirect("hr:employee_list")

        qs = Employee.objects.filter(id__in=ids)

        if action == "archive":
            qs.update(active=False)
            messages.success(request, f"{qs.count()} employees archived.")

        elif action == "unarchive":
            qs.update(active=True)
            messages.success(request, f"{qs.count()} employees restored.")

        return redirect("hr:employee_list")

