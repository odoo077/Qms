# hr/views.py
"""
HR Views (Odoo-like behavior)

Design principles:
- Company scope is enforced via CompanyOwnedMixin / CompanyScopeManager
- ACL is enforced via AccessControlledMixin + ACLManager
- No implicit magic or hidden permissions
- Views are thin: logic lives in models/forms
"""
from django.shortcuts import redirect, get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST
from django.contrib import messages
from base.company_context import get_company_id, set_company
from base.models import Company
from .models import Department, Job, Employee, get_root_departments, build_department_tree, EmployeeStatusHistory, \
    EmployeeEducation, EmployeeStatus
from .forms import DepartmentForm, JobForm, EmployeeForm, EmployeeEducationForm
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q, F, Value, Prefetch
from django.db.models.functions import Coalesce, Greatest
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.views.generic import TemplateView
from django.views.generic.edit import UpdateView
from base.company_context import get_allowed_company_ids
from base.views import BaseScopedListView, BaseScopedDetailView, BaseScopedCreateView, BaseScopedUpdateView
from skills.models import EmployeeSkill
from assets.models import AssetAssignment
from .services import change_employee_status
from django.views.generic import View, DeleteView

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
        qs = (
            super()
            .get_queryset()
            .select_related("company", "department")
            .annotate(
                employees_count=Count(
                    "employees",
                    filter=Q(employees__active=True),
                    distinct=True,
                ),
            )
            .annotate(
                vacancies=Greatest(
                    Value(0),
                    Coalesce(F("no_of_recruitment"), Value(0))
                    - Coalesce(F("employees_count"), Value(0)),
                )
            )
            .order_by("name")
        )
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
        return (
            Job.objects
            .select_related("company", "department")
            .prefetch_related(
                "employees__department",
                "employees__manager",
            )
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
            job.employees
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
            .select_related(
                "company",
                "department",
                "job",
                "manager",
                "user",
                "current_status",
            )
        )

        request = self.request
        SESSION_KEY = "employee_list_filters"

        # --------------------------------------------------
        # 1) Load filters:
        #    - If GET is empty → restore from session
        # --------------------------------------------------
        if request.GET:
            params = request.GET.copy()
        else:
            params = request.session.get(SESSION_KEY, {}).copy()

        # --------------------------------------------------
        # 2) Save filters to session (exclude pagination)
        # --------------------------------------------------
        if params:
            request.session[SESSION_KEY] = {
                k: v for k, v in params.items()
                if v and k != "page"
            }

        # --------------------------------------------------
        # 3) Global search
        # --------------------------------------------------
        q = (params.get("q") or "").strip()
        if q:
            qs = qs.filter(
                Q(name__icontains=q)
                | Q(user__email__icontains=q)
                | Q(job__name__icontains=q)
                | Q(department__name__icontains=q)
                | Q(manager__name__icontains=q)
                | Q(company__name__icontains=q)
            )

        # --------------------------------------------------
        # 4) Filters
        # --------------------------------------------------
        company_id = params.get("company")
        if company_id:
            qs = qs.filter(company_id=company_id)

        department_id = params.get("department")
        if department_id:
            qs = qs.filter(department_id=department_id)

        job_id = params.get("job")
        if job_id:
            qs = qs.filter(job_id=job_id)

        manager_id = params.get("manager")
        if manager_id:
            qs = qs.filter(manager_id=manager_id)

        status_id = params.get("status")
        if status_id:
            qs = qs.filter(current_status_id=status_id)

        # --------------------------------------------------
        # 5) Record visibility (Active / Archived)
        # --------------------------------------------------
        record = (params.get("record") or "").strip()

        if record == "active":
            qs = qs.filter(active=True)
        elif record == "archived":
            qs = qs.filter(active=False)
        # else → show all (default behavior unchanged)

        return qs.order_by("name")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        ctx["companies"] = Company.objects.all().order_by("name")
        ctx["departments"] = Department.objects.all().order_by("complete_name")
        ctx["jobs"] = Job.objects.all().order_by("name")
        ctx["managers"] = Employee.objects.all().order_by("name")
        ctx["statuses"] = EmployeeStatus.objects.filter(active=True).order_by("sequence")

        return ctx


class EmployeeDetailView(LoginRequiredMixin, BaseScopedDetailView):
    """
    Employee detail view (Odoo-like)

    - Company scoped
    - No ACL enforcement (as requested)
    - Includes Skills + Assets
    """

    model = Employee
    template_name = "hr/employee_detail.html"
    context_object_name = "employee"

    # --------------------------------------------------
    # Company Scope Enforcement
    # --------------------------------------------------
    def _enforce_object_scope_or_404(self, obj):
        allowed_company_ids = get_allowed_company_ids(self.request)
        if allowed_company_ids and obj.company_id not in allowed_company_ids:
            raise PermissionDenied("Employee is outside active company scope.")
        return obj

    # --------------------------------------------------
    # Optimized Queryset
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
                Prefetch(
                    "asset_assignments",
                    queryset=(
                        AssetAssignment.objects
                        .select_related("asset", "company")
                        .order_by("-date_from", "-id")
                    ),
                ),
            )
        )

    # --------------------------------------------------
    # Context Data
    # --------------------------------------------------
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        employee = self.object

        # -------- UI Flags
        ctx["can_edit"] = True

        # -------- Management Chain
        chain = []
        node = employee.manager
        while node:
            chain.append(node)
            node = node.manager
        ctx["manager_chain"] = chain

        # -------- Subordinates
        ctx["subordinates"] = employee.managed_employees.filter(active=True)

        # ==================================================
        # Employee Skills
        # ==================================================
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

        # ==================================================
        # Asset Assignments (THIS IS THE IMPORTANT PART)
        # ==================================================
        asset_assignments = (
            employee.asset_assignments
            .select_related("asset", "company")
            .order_by("-date_from", "-id")
        )

        ctx["asset_assignments"] = asset_assignments
        ctx["current_asset_assignments"] = asset_assignments.filter(date_to__isnull=True)
        ctx["employee_assets_open"] = ctx["current_asset_assignments"]
        ctx["employee_assets_history"] = asset_assignments

        # Can assign new asset only if no open assignment exists
        ctx["can_assign_asset"] = not ctx["current_asset_assignments"].exists()

        # ==================================================
        # Employee Statuses (Change Status Modal)
        # ==================================================
        ctx["employee_statuses"] = (
            EmployeeStatus.objects
            .filter(active=True)
            .order_by("sequence")
        )

        # -------- Status History
        ctx["status_history"] = (
            EmployeeStatusHistory.objects
            .filter(employee=employee)
            .select_related(
                "status",
                "changed_by",
            )
            .order_by("-changed_at")
        )

        # -------- Education
        ctx["education_records"] = (
            EmployeeEducation.objects
            .filter(employee=employee)
            .order_by("-end_year", "-start_year")
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


# ==========================================================
# Employee Status Change
# ==========================================================

class EmployeeChangeStatusView(View):
    """
    Handle employee status change (POST only).
    """

    def post(self, request, pk):
        employee = get_object_or_404(Employee, pk=pk)

        status_id = request.POST.get("status")
        reason = request.POST.get("reason", "").strip()
        note = request.POST.get("note", "").strip()

        if not status_id or not reason:
            messages.error(request, "Status and reason are required.")
            return redirect(employee.get_absolute_url())

        status = get_object_or_404(EmployeeStatus, pk=status_id)

        try:
            change_employee_status(
                employee=employee,
                new_status=status,
                reason=reason,
                note=note,
                changed_by=request.user if request.user.is_authenticated else None,
            )
            messages.success(
                request,
                f"Employee status changed to '{status.name}'."
            )
        except Exception as exc:
            messages.error(request, str(exc))

        return redirect(employee.get_absolute_url())

# ==========================================================
# Employee Education Form
# ==========================================================

@method_decorator(require_POST, name="dispatch")
class EmployeeEducationCreateView(LoginRequiredMixin, View):
    def post(self, request, employee_id):
        employee = get_object_or_404(Employee, pk=employee_id)

        form = EmployeeEducationForm(request.POST)
        if form.is_valid():
            edu = form.save(commit=False)
            edu.employee = employee
            edu.save()
            messages.success(request, "Education record added.")
        else:
            messages.error(request, "Failed to add education record.")

        return redirect(employee.get_absolute_url())

@method_decorator(require_POST, name="dispatch")
class EducationUpdateView(LoginRequiredMixin, View):
    def post(self, request, pk):
        education = get_object_or_404(EmployeeEducation, pk=pk)

        # company scope (safe)
        allowed = get_allowed_company_ids(request)
        if allowed and education.employee.company_id not in allowed:
            raise PermissionDenied("Outside company scope.")

        form = EmployeeEducationForm(
            request.POST,
            instance=education,
        )

        if form.is_valid():
            form.save()
            messages.success(request, "Education record updated successfully.")
        else:
            messages.error(request, "Failed to update education record.")

        return redirect(education.employee.get_absolute_url())

class EducationDeleteView(LoginRequiredMixin, DeleteView):
    model = EmployeeEducation
    template_name = "partials/confirm_delete.html"

    def get_success_url(self):
        return self.object.employee.get_absolute_url()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["object_label"] = "Education Record"
        ctx["back_url"] = self.object.employee.get_absolute_url()
        return ctx

    def dispatch(self, request, *args, **kwargs):
        obj = self.get_object()
        allowed = get_allowed_company_ids(request)
        if allowed and obj.employee.company_id not in allowed:
            raise PermissionDenied("Outside company scope.")
        return super().dispatch(request, *args, **kwargs)
