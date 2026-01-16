# hr/views.py
"""
HR Views (Odoo-like behavior)

Design principles:
- Company scope is enforced via CompanyOwnedMixin / CompanyScopeManager
- No implicit magic or hidden permissions
- Views are thin: logic lives in models/forms
"""
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST
from django.contrib import messages
from base.company_context import get_company_id, set_company
from base.models import Company
from skills.services import compute_employee_job_gap, compute_employee_job_fit_score, \
    compute_employee_career_eligibility, compute_career_blocking_factors, compute_training_recommendations
from .models import Department, Job, Employee, get_root_departments, build_department_tree, EmployeeStatusHistory, \
    EmployeeEducation, EmployeeStatus, CareerPolicy
from .forms import DepartmentForm, JobForm, EmployeeForm, EmployeeEducationForm, CareerPolicyForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q, F, Value, Prefetch
from django.db.models.functions import Coalesce, Greatest
from django.http import HttpResponse, Http404
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.views.generic import TemplateView
from django.views.generic.edit import UpdateView
from base.company_context import get_allowed_company_ids
from base.views import BaseScopedListView, BaseScopedDetailView, BaseScopedCreateView, BaseScopedUpdateView, \
    BaseScopedDeleteView
from skills.models import EmployeeSkill, JobSkill
from assets.models import AssetAssignment
from .services import change_employee_status
from django.views.generic import View, DeleteView
from django.urls import reverse
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from hr.models import JobCareerPath
from hr.forms import JobCareerPathForm
from django.core.exceptions import ValidationError



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

        return ctx


class DepartmentDetailView(LoginRequiredMixin, BaseScopedDetailView):
    """
    Department Detail View (Odoo-like behavior)

    Rules:
    - Company scoped via BaseScopedDetailView (consistent with the app)
    """

    model = Department
    template_name = "hr/department_detail.html"

    def get_object(self, queryset=None):
        obj = super(BaseScopedDetailView, self).get_object(queryset=queryset)

        # تحقق نطاق الشركة فقط
        active_ids = get_allowed_company_ids(self.request)
        if active_ids and obj.company_id not in active_ids:
            raise HttpResponse(status=404)

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

        return ctx


class DepartmentCreateView(
    LoginRequiredMixin,
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
            return self.form_invalid(form)

        # enforce scope
        if allowed and company.id not in allowed:
            return self.form_invalid(form)

        form.instance.company = company

        # protect parent/company mismatch early (before model.clean message confusion)
        if form.instance.parent_id and form.instance.parent.company_id != form.instance.company_id:
            form.add_error("parent", "Parent department must belong to the same company.")
            return self.form_invalid(form)

        return super().form_valid(form)
















class DepartmentUpdateView(
    LoginRequiredMixin,
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

    def get_queryset(self):
        return Department.objects.select_related("company", "parent", "manager")

    def _enforce_object_scope_or_404(self, obj):
        allowed_company_ids = get_allowed_company_ids(self.request) or []
        if allowed_company_ids and obj.company_id not in allowed_company_ids:
            raise Http404
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
    - Company scope ONLY
    - NO record-level ACL
    """
    model = Job
    template_name = "hr/job_list.html"
    paginate_by = 50

    def filter_queryset(self, qs):
        """
        Disable record-level ACL.
        Keep company scope filtering only.
        """
        return qs

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
        return ctx


class JobDetailView(LoginRequiredMixin, BaseScopedDetailView):
    """
    Job Detail (STRUCTURAL):
    - Company scope ONLY
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
        allowed_company_ids = get_allowed_company_ids(self.request)
        if allowed_company_ids and obj.company_id not in allowed_company_ids:
            raise Http404
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

        return ctx


class JobCreateView(
    LoginRequiredMixin,
    BaseScopedCreateView,
):
    """
    Create new Job:
    - Company scope enforced
    - NO permissions
    - NO record-level ACL
    """
    model = Job
    form_class = JobForm
    template_name = "hr/job_form.html"
    success_url = reverse_lazy("hr:job_list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        allowed_company_ids = get_allowed_company_ids(self.request)
        if hasattr(self.form_class, "accepts_allowed_company_ids"):
            kwargs["allowed_company_ids"] = allowed_company_ids
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        allowed_company_ids = get_allowed_company_ids(self.request)
        if allowed_company_ids:
            initial.setdefault("company", allowed_company_ids[0])
        return initial


class JobUpdateView(
    LoginRequiredMixin,
    BaseScopedUpdateView,
):
    """
    Job Update (STRUCTURAL):
    - Company scope only
    - NO permissions
    - NO record-level ACL
    """
    model = Job
    form_class = JobForm
    template_name = "hr/job_form.html"
    success_url = reverse_lazy("hr:job_list")

    def get_queryset(self):
        return Job.objects.select_related("company", "department")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        allowed_ids = get_allowed_company_ids(self.request)
        if hasattr(self.form_class, "accepts_allowed_company_ids"):
            kwargs["allowed_company_ids"] = allowed_ids
        return kwargs

    def _enforce_object_scope_or_404(self, obj):
        allowed_ids = get_allowed_company_ids(self.request)
        if allowed_ids and obj.company_id not in allowed_ids:
            raise Http404
        return obj

    def form_valid(self, form):
        form.instance.company_id = self.object.company_id
        return UpdateView.form_valid(self, form)


class JobEmployeeUpdateView(
    LoginRequiredMixin,
    BaseScopedUpdateView,
):
    """
    Change employee job (Odoo-like, FINAL).

    Rules:
    - Company scope only
    - NO permissions
    - NO record-level ACL
    """
    model = Employee
    fields = ("job",)
    template_name = "hr/job_employee_form.html"
    success_url = reverse_lazy("hr:employee_list")

    def get_queryset(self):
        return Employee.objects.select_related(
            "company",
            "job",
            "department",
        )

    def _enforce_object_scope_or_404(self, obj):
        allowed_company_ids = get_allowed_company_ids(self.request)
        if allowed_company_ids and obj.company_id not in allowed_company_ids:
            raise Http404
        return obj

    def form_valid(self, form):
        form.instance.company_id = self.object.company_id

        job = form.instance.job
        if job and job.company_id != form.instance.company_id:
            raise ValidationError(
                "Selected job must belong to the same company as the employee."
            )

        return UpdateView.form_valid(self, form)


class JobDeleteView(
    LoginRequiredMixin,
    BaseScopedDeleteView,
):
    """
    Delete Job (STRUCTURAL, FINAL)

    Rules:
    - Company scope only
    - NO permissions
    - NO record-level ACL
    """

    model = Job
    template_name = "partials/confirm_delete.html"
    success_url = reverse_lazy("hr:job_list")

    object_label = "Job"
    confirm_label = "Delete Job"

    def get_queryset(self):
        return Job.objects.select_related("company", "department")

    def _enforce_object_scope_or_404(self, obj):
        allowed_company_ids = get_allowed_company_ids(self.request)
        if allowed_company_ids and obj.company_id not in allowed_company_ids:
            raise Http404
        return obj

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        return DeleteView.delete(self, request, *args, **kwargs)




















# ==========================================================
# Career Policy - List
# ==========================================================
class CareerPolicyListView(LoginRequiredMixin, BaseScopedListView):
    model = CareerPolicy
    template_name = "hr/career_policy_list.html"
    context_object_name = "policies"
    paginate_by = 50

    def get_queryset(self):
        qs = super().get_queryset().select_related("company")
        return qs.order_by("company__name", "-active", "-id")


# ==========================================================
# Career Policy - Create
# ==========================================================
class CareerPolicyCreateView(LoginRequiredMixin, CreateView):
    model = CareerPolicy
    form_class = CareerPolicyForm
    template_name = "hr/career_policy_form.html"
    success_url = reverse_lazy("hr:career_policy_list")

    def form_valid(self, form):
        allowed = get_allowed_company_ids(self.request)

        # Enforce company scope (NO permissions)
        if allowed and form.instance.company_id not in allowed:
            return self.form_invalid(form)

        return super().form_valid(form)


# ==========================================================
# Career Policy - Update
# ==========================================================
class CareerPolicyUpdateView(LoginRequiredMixin, UpdateView):
    model = CareerPolicy
    form_class = CareerPolicyForm
    template_name = "hr/career_policy_form.html"
    success_url = reverse_lazy("hr:career_policy_list")

    def get_queryset(self):
        return CareerPolicy.objects.select_related("company")

    def dispatch(self, request, *args, **kwargs):
        obj = self.get_object()
        allowed = get_allowed_company_ids(request)

        if allowed and obj.company_id not in allowed:
            return redirect("hr:career_policy_list")

        return super().dispatch(request, *args, **kwargs)


# ==========================================================
# Career Policy - Delete
# ==========================================================
class CareerPolicyDeleteView(LoginRequiredMixin, DeleteView):
    model = CareerPolicy
    template_name = "partials/confirm_delete.html"
    success_url = reverse_lazy("hr:career_policy_list")

    def dispatch(self, request, *args, **kwargs):
        obj = self.get_object()
        allowed = get_allowed_company_ids(request)

        if allowed and obj.company_id not in allowed:
            return redirect("hr:career_policy_list")

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["object_label"] = "Career Policy"
        ctx["confirm_label"] = "Delete Policy"
        ctx["back_url"] = reverse_lazy("hr:career_policy_list")
        return ctx


# ==========================================================
# Career Path
# ==========================================================

class JobCareerPathListView(LoginRequiredMixin, ListView):
    model = JobCareerPath
    template_name = "hr/jobcareerpath_list.html"
    paginate_by = 50
    login_url = "base:login"

    def get_queryset(self):
        return (
            JobCareerPath.objects
            .select_related("from_job", "to_job")
            .order_by("from_job__name", "sequence")
        )


class JobCareerPathCreateView(LoginRequiredMixin, CreateView):
    model = JobCareerPath
    form_class = JobCareerPathForm
    template_name = "hr/jobcareerpath_form.html"
    success_url = reverse_lazy("hr:jobcareerpath_list")
    login_url = "base:login"


class JobCareerPathUpdateView(LoginRequiredMixin, UpdateView):
    model = JobCareerPath
    form_class = JobCareerPathForm
    template_name = "hr/jobcareerpath_form.html"
    success_url = reverse_lazy("hr:jobcareerpath_list")
    login_url = "base:login"


class JobCareerPathDeleteView(LoginRequiredMixin, DeleteView):
    model = JobCareerPath
    template_name = "partials/confirm_delete.html"
    success_url = reverse_lazy("hr:jobcareerpath_list")
    login_url = "base:login"


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
    paginate_by = 25
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

        employees = list(qs.order_by("name"))

        for emp in employees:
            if emp.job_id:
                fit = compute_employee_job_fit_score(emp)
                emp.readiness_score = fit.score
                emp.readiness_label = fit.label
            else:
                emp.readiness_score = None
                emp.readiness_label = "N/A"

        return employees

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

    Logic Summary:
    - job_fit            : Current job readiness
    - career_path        : Promotion path
    - row.eligible       : Promotion eligibility (strict)
    - next_role          : Next logical role (even if not eligible)
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

        # ==================================================
        # Current Role – Readiness
        # ==================================================
        skill_gap = compute_employee_job_gap(employee)
        job_fit = compute_employee_job_fit_score(employee)

        ctx["skill_gap"] = skill_gap
        ctx["job_fit"] = job_fit

        # ==================================================
        # Career Path (raw)
        # ==================================================
        career_path = compute_employee_career_eligibility(employee) or []
        ctx["career_path"] = career_path

        # ==================================================
        # Employee Skill Progress Map
        # ==================================================
        employee_skill_progress = {
            es.skill_id: es.skill_level.level_progress
            for es in (
                EmployeeSkill.objects
                .filter(employee=employee, active=True)
                .select_related("skill_level")
            )
            if es.skill_level_id
        }

        # ==================================================
        # Promotion Eligibility (STRICT)
        # ==================================================
        for row in career_path:
            job = row.get("job")
            if not job:
                row["eligible"] = False
                continue

            required_skills = (
                JobSkill.objects
                .filter(job=job, active=True)
                .select_related("min_level")
            )

            missing = 0
            gap = 0

            for req in required_skills:
                emp_progress = employee_skill_progress.get(req.skill_id)

                if emp_progress is None:
                    missing += 1
                elif emp_progress < req.min_level.level_progress:
                    gap += 1

            row["eligible"] = (missing == 0 and gap == 0)
            row["missing_count"] = missing
            row["gap_count"] = gap

        # ==================================================
        # Next Role (Logical, not eligibility-based)
        # ==================================================
        next_role = None
        if career_path:
            for row in career_path:
                if row.get("job"):
                    next_role = row["job"]
                    break

        ctx["next_role"] = next_role
        ctx["next_eligible_job"] = next_role

        # ==================================================
        # Next Role – Skill Readiness
        # ==================================================
        ctx["next_role_missing_skills"] = []
        ctx["next_role_gap_skills"] = []
        ctx["next_role_met_skills"] = []

        if next_role:
            required_skills = (
                JobSkill.objects
                .filter(job=next_role, active=True)
                .select_related(
                    "skill",
                    "min_level",
                    "min_level__skill_type",
                )
                .order_by("skill__skill_type__sequence", "skill__name")
            )

            employee_skills = {
                es.skill_id: es
                for es in (
                    EmployeeSkill.objects
                    .filter(employee=employee, active=True)
                    .select_related("skill", "skill_level")
                )
            }

            for req in required_skills:
                emp_skill = employee_skills.get(req.skill_id)

                if not emp_skill:
                    ctx["next_role_missing_skills"].append(req)
                    continue

                if emp_skill.skill_level.level_progress < req.min_level.level_progress:
                    ctx["next_role_gap_skills"].append({
                        "skill": req.skill,
                        "required": req.min_level,
                        "current": emp_skill.skill_level,
                    })
                else:
                    ctx["next_role_met_skills"].append(req)

        # ==================================================
        # Training & Blockers
        # ==================================================
        training_recommendations = compute_training_recommendations(employee)
        ctx["training_recommendations"] = training_recommendations
        ctx["training_recommendations_top"] = training_recommendations[:3]
        ctx["career_blockers"] = compute_career_blocking_factors(employee)

        # ==================================================
        # Manager Chain & Subordinates
        # ==================================================
        chain = []
        node = employee.manager
        while node:
            chain.append(node)
            node = node.manager
        ctx["manager_chain"] = chain

        ctx["subordinates"] = employee.managed_employees.filter(active=True)

        # ==================================================
        # Employee Skills
        # ==================================================
        ctx["employee_skills"] = (
            EmployeeSkill.objects
            .filter(employee=employee)
            .select_related("skill_type", "skill", "skill_level")
            .order_by("skill_type__name", "skill__name")
        )

        # ==================================================
        # Assets
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

        # ==================================================
        # Statuses & Education
        # ==================================================
        ctx["employee_statuses"] = EmployeeStatus.objects.filter(active=True).order_by("sequence")

        ctx["status_history"] = (
            EmployeeStatusHistory.objects
            .filter(employee=employee)
            .select_related("status", "changed_by")
            .order_by("-changed_at")
        )

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
    """
    Bulk archive / restore employees.
    - Company scope enforced
    """

    def post(self, request):
        action = request.POST.get("action")
        ids = request.POST.getlist("ids")

        if not ids:
            messages.warning(request, "No employees selected.")
            return redirect("hr:employee_list")

        allowed_company_ids = get_allowed_company_ids(request)

        qs = Employee.objects.filter(id__in=ids)

        # Enforce company scope
        if allowed_company_ids:
            qs = qs.filter(company_id__in=allowed_company_ids)

        if not qs.exists():
            messages.error(request, "No valid employees in active company scope.")
            return redirect("hr:employee_list")

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

class EmployeeChangeStatusView(LoginRequiredMixin, View):
    """
    Handle employee status change (POST only).

    Rules:
    - Login required
    - Company scope enforced
    - Business logic delegated to service layer
    """

    def post(self, request, pk):
        employee = get_object_or_404(Employee, pk=pk)

        # Enforce company scope
        allowed_company_ids = get_allowed_company_ids(request)
        if allowed_company_ids and employee.company_id not in allowed_company_ids:
            raise PermissionDenied("Employee outside active company scope.")

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
                changed_by=request.user,
            )
            messages.success(
                request,
                f"Employee status changed to '{status.name}'."
            )
        except Exception as exc:
            messages.error(request, str(exc))

        return redirect(employee.get_absolute_url())















# ==========================================================
# Employee Education
# ==========================================================

@method_decorator(require_POST, name="dispatch")
class EmployeeEducationCreateView(LoginRequiredMixin, View):
    """
    Create education record for employee.
    - Login required
    - Company scope enforced
    """

    def post(self, request, employee_id):
        employee = get_object_or_404(Employee, pk=employee_id)

        # Enforce company scope
        allowed = get_allowed_company_ids(request)
        if allowed and employee.company_id not in allowed:
            raise PermissionDenied("Outside company scope.")

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
    """
    Update education record.
    - Login required
    - Company scope enforced
    """

    def post(self, request, pk):
        education = get_object_or_404(EmployeeEducation, pk=pk)

        # Enforce company scope
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
    """
    Delete education record.
    - Login required
    - Company scope enforced
    """

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
