# hr/views.py
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Q
from django.urls import reverse_lazy
from django.views.generic import DetailView
from base.views import (
    BaseScopedListView,
    BaseScopedCreateView,
    BaseScopedUpdateView,
    apply_search_filters, BaseScopedDetailView,
)
from .models import Department, Job, Employee
from .forms import DepartmentForm, JobForm, EmployeeForm


# ----- Departments -----
class DepartmentListView(LoginRequiredMixin, BaseScopedListView):
    model = Department
    template_name = "hr/department_list.html"
    paginate_by = 24

    def get_queryset(self):
        # الغي فلترة ACL مؤقتًا حتى تظهر الشجرة بالكامل
        base_qs = Department.objects.all()
        qs = (Department.objects
              .filter(pk__in=base_qs.values("pk"))
              .select_related("company", "parent", "manager")
              .prefetch_related("children")
              .order_by("complete_name", "name"))

        qs = apply_search_filters(self.request, qs,
                                  search_fields=["name", "complete_name", "manager__name", "parent__name"])
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_add_department"] = self.request.user.has_perm("hr.add_department")

        active_ids = self._active_company_ids()

        # أولاً: احصل على الـ IDs من with_acl فقط (بدون filter بعد union)
        base_acl_ids = Department.acl_objects.with_acl("change").values("pk")

        # ثم ابنِ QuerySet جديد آمن من Manager العادي
        qs_acl = Department.objects.filter(pk__in=base_acl_ids)
        if active_ids:
            qs_acl = qs_acl.filter(company_id__in=active_ids)

        ctx["dept_change_ids"] = set(qs_acl.values_list("id", flat=True))
        return ctx


class DepartmentCreateView(LoginRequiredMixin, PermissionRequiredMixin, BaseScopedCreateView):
    permission_required = "hr.add_department"
    model = Department
    form_class = DepartmentForm
    template_name = "hr/department_form.html"
    success_url = reverse_lazy("hr:department_list")


class DepartmentUpdateView(LoginRequiredMixin, PermissionRequiredMixin, BaseScopedUpdateView):
    permission_required = "hr.change_department"
    model = Department
    form_class = DepartmentForm
    template_name = "hr/department_form.html"
    success_url = reverse_lazy("hr:department_list")


# ✅ استخدم BaseScopedDetailView بدلاً من DetailView
class DepartmentDetailView(LoginRequiredMixin, BaseScopedDetailView):
    model = Department
    template_name = "hr/department_detail.html"

    def get_queryset(self):
        # ✅ super() يطبق ACL + Company scope
        return (super().get_queryset()
                .select_related("company", "parent", "manager"))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        active_ids = self._active_company_ids()
        base_acl_ids = Department.acl_objects.with_acl("change").values("pk")
        qs_acl = Department.objects.filter(pk__in=base_acl_ids)
        if active_ids:
            qs_acl = qs_acl.filter(company_id__in=active_ids)

        ctx["dept_change_ids"] = set(qs_acl.values_list("id", flat=True))
        return ctx


# ----- JOBS -----

class JobListView(LoginRequiredMixin, BaseScopedListView):
    model = Job
    template_name = "hr/job_list.html"
    paginate_by = 24

    def get_queryset(self):
        # ❗ IDs فقط لتجنب UNION → filter()
        base_qs = super().get_queryset()
        qs = (Job.objects
                .filter(pk__in=base_qs.values("pk"))
                .select_related("company", "department")
                .order_by("name"))
        qs = apply_search_filters(self.request, qs,
                                  search_fields=["name", "department__name"])
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_add_job"] = self.request.user.has_perm("hr.add_job")

        active_ids = self._active_company_ids()
        base_acl_ids = Job.acl_objects.with_acl("change").values("pk")
        qs_acl = Job.objects.filter(pk__in=base_acl_ids)
        if active_ids:
            qs_acl = qs_acl.filter(company_id__in=active_ids)

        ctx["job_change_ids"] = set(qs_acl.values_list("id", flat=True))
        return ctx


class JobCreateView(LoginRequiredMixin, PermissionRequiredMixin, BaseScopedCreateView):
    permission_required = "hr.add_job"
    model = Job
    form_class = JobForm
    template_name = "hr/job_form.html"
    success_url = reverse_lazy("hr:job_list")


class JobUpdateView(LoginRequiredMixin, PermissionRequiredMixin, BaseScopedUpdateView):
    permission_required = "hr.change_job"
    model = Job
    form_class = JobForm
    template_name = "hr/job_form.html"
    success_url = reverse_lazy("hr:job_list")


# ✅ DetailView → BaseScopedDetailView
class JobDetailView(LoginRequiredMixin, BaseScopedDetailView):
    model = Job
    template_name = "hr/job_detail.html"

    def get_queryset(self):
        return (super().get_queryset()
                .select_related("company", "department"))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        active_ids = self._active_company_ids()
        base_acl_ids = Job.acl_objects.with_acl("change").values("pk")
        qs_acl = Job.objects.filter(pk__in=base_acl_ids)
        if active_ids:
            qs_acl = qs_acl.filter(company_id__in=active_ids)

        ctx["job_change_ids"] = set(qs_acl.values_list("id", flat=True))
        return ctx


# ----- EMPLOYEES -----

class EmployeeListView(LoginRequiredMixin, BaseScopedListView):
    model = Employee
    template_name = "hr/employee_list.html"
    paginate_by = 24

    def get_queryset(self):
        # ❗ IDs فقط لتجنب UNION → filter()
        base_qs = super().get_queryset()
        qs = (Employee.objects
                .filter(pk__in=base_qs.values("pk"))
                .select_related("company", "department", "job")
                .order_by("name"))
        qs = apply_search_filters(self.request, qs,
                                  search_fields=["name", "department__name", "job__name",
                                                 "work_email", "work_phone"])
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_add_employee"] = self.request.user.has_perm("hr.add_employee")

        active_ids = self._active_company_ids()
        base_acl_ids = Employee.acl_objects.with_acl("change").values("pk")
        qs_acl = Employee.objects.filter(pk__in=base_acl_ids)
        if active_ids:
            qs_acl = qs_acl.filter(company_id__in=active_ids)

        ctx["emp_change_ids"] = set(qs_acl.values_list("id", flat=True))
        return ctx


class EmployeeCreateView(LoginRequiredMixin, PermissionRequiredMixin, BaseScopedCreateView):
    permission_required = "hr.add_employee"
    model = Employee
    form_class = EmployeeForm
    template_name = "hr/employee_form.html"
    success_url = reverse_lazy("hr:employee_list")


class EmployeeUpdateView(LoginRequiredMixin, PermissionRequiredMixin, BaseScopedUpdateView):
    permission_required = "hr.change_employee"
    model = Employee
    form_class = EmployeeForm
    template_name = "hr/employee_form.html"
    success_url = reverse_lazy("hr:employee_list")


# ✅ DetailView → BaseScopedDetailView
class EmployeeDetailView(LoginRequiredMixin, BaseScopedDetailView):
    model = Employee
    template_name = "hr/employee_detail.html"

    def get_queryset(self):
        return (super().get_queryset()
                .select_related("company", "department", "job"))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        active_ids = self._active_company_ids()
        base_acl_ids = Employee.acl_objects.with_acl("change").values("pk")
        qs_acl = Employee.objects.filter(pk__in=base_acl_ids)
        if active_ids:
            qs_acl = qs_acl.filter(company_id__in=active_ids)

        ctx["emp_change_ids"] = set(qs_acl.values_list("id", flat=True))
        return ctx
