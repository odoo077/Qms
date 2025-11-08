# hr/views.py
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DetailView
from base.views import BaseScopedListView, apply_search_filters
from .models import Department, Job , Employee
from .forms import DepartmentForm, JobForm, EmployeeForm


# ----- Departments -----
class DepartmentListView(LoginRequiredMixin, BaseScopedListView):
    model = Department
    template_name = "hr/department_list.html"
    paginate_by = 24

    def get_queryset(self):
        ids = Department.acl_objects.with_acl("view").values("id")
        qs = (Department.objects.filter(id__in=ids)
              .select_related("company", "parent", "manager")
              .order_by("complete_name", "name"))
        qs = apply_search_filters(self.request, qs,
                                  search_fields=["name", "complete_name", "manager__name", "parent__name"])
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_add_department"] = self.request.user.has_perm("hr.add_department")
        change_ids = Department.acl_objects.with_acl("change").values_list("id", flat=True)
        ctx["dept_change_ids"] = set(change_ids)
        return ctx

class DepartmentCreateView(LoginRequiredMixin, CreateView):
    model = Department
    form_class = DepartmentForm
    template_name = "hr/department_form.html"
    success_url = reverse_lazy("hr:department_list")

class DepartmentUpdateView(LoginRequiredMixin, UpdateView):
    model = Department
    form_class = DepartmentForm
    template_name = "hr/department_form.html"
    success_url = reverse_lazy("hr:department_list")

class DepartmentDetailView(LoginRequiredMixin, DetailView):
    model = Department
    template_name = "hr/department_detail.html"

    def get_queryset(self):
        ids = Department.acl_objects.with_acl("view").values("id")
        return Department.objects.filter(id__in=ids).select_related("company", "parent", "manager")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        change_ids = Department.acl_objects.with_acl("change").values_list("id", flat=True)
        ctx["dept_change_ids"] = set(change_ids)
        return ctx


# ----- JOBS -----

class JobListView(LoginRequiredMixin, BaseScopedListView):
    model = Job
    template_name = "hr/job_list.html"
    paginate_by = 24

    def get_queryset(self):
        ids = Job.acl_objects.with_acl("view").values("id")
        qs = (Job.objects.filter(id__in=ids)
              .select_related("company", "department")
              .order_by("name"))
        qs = apply_search_filters(self.request, qs, search_fields=["name", "department__name"])
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_add_job"] = self.request.user.has_perm("hr.add_job")
        change_ids = Job.acl_objects.with_acl("change").values_list("id", flat=True)
        ctx["job_change_ids"] = set(change_ids)
        return ctx

class JobCreateView(LoginRequiredMixin, CreateView):
    model = Job
    form_class = JobForm
    template_name = "hr/job_form.html"
    success_url = reverse_lazy("hr:job_list")

class JobUpdateView(LoginRequiredMixin, UpdateView):
    model = Job
    form_class = JobForm
    template_name = "hr/job_form.html"
    success_url = reverse_lazy("hr:job_list")

class JobDetailView(LoginRequiredMixin, DetailView):
    model = Job
    template_name = "hr/job_detail.html"

    def get_queryset(self):
        ids = Job.acl_objects.with_acl("view").values("id")
        return Job.objects.filter(id__in=ids).select_related("company", "department")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        change_ids = Job.acl_objects.with_acl("change").values_list("id", flat=True)
        ctx["job_change_ids"] = set(change_ids)
        return ctx


# ----- EMPLOYEES -----

class EmployeeListView(LoginRequiredMixin, BaseScopedListView):
    model = Employee
    template_name = "hr/employee_list.html"
    paginate_by = 24

    def get_queryset(self):
        ids = Employee.acl_objects.with_acl("view").values("id")
        qs = (Employee.objects.filter(id__in=ids)
              .select_related("company", "department", "job")
              .order_by("name"))
        qs = apply_search_filters(self.request, qs,
                                  search_fields=["name", "department__name", "job__name", "work_email", "work_phone"])
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_add_employee"] = self.request.user.has_perm("hr.add_employee")
        change_ids = Employee.acl_objects.with_acl("change").values_list("id", flat=True)
        ctx["emp_change_ids"] = set(change_ids)
        return ctx

class EmployeeCreateView(LoginRequiredMixin, CreateView):
    model = Employee
    form_class = EmployeeForm
    template_name = "hr/employee_form.html"
    success_url = reverse_lazy("hr:employee_list")

class EmployeeUpdateView(LoginRequiredMixin, UpdateView):
    model = Employee
    form_class = EmployeeForm
    template_name = "hr/employee_form.html"
    success_url = reverse_lazy("hr:employee_list")

class EmployeeDetailView(LoginRequiredMixin, DetailView):
    model = Employee
    template_name = "hr/employee_detail.html"

    def get_queryset(self):
        ids = Employee.acl_objects.with_acl("view").values("id")
        return Employee.objects.filter(id__in=ids).select_related("company", "department", "job")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        change_ids = Employee.acl_objects.with_acl("change").values_list("id", flat=True)
        ctx["emp_change_ids"] = set(change_ids)
        return ctx
