# file: hr/views.py

from django.core.exceptions import PermissionDenied
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView, UpdateView

from hr.models import Department, Employee, Job, get_root_departments, build_department_tree
from hr.forms import DepartmentForm, EmployeeForm, JobForm
from hr.access import (
    can_view_department,
    can_edit_department,
    can_view_employee,
    can_edit_employee,
)


# ============================================================
# Departments
# ============================================================

class DepartmentListView(ListView):
    model = Department
    template_name = "hr/department_list.html"
    context_object_name = "tree"

    def get_queryset(self):
        """Return only the root nodes of the tree."""
        user = self.request.user
        roots = get_root_departments(user.company_ids[0])
        return build_department_tree(roots)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        # كل ما يحتاجه التمبلت ليعمل بدون أي أخطاء
        ctx["tree"] = ctx["tree"]  # شجرة الأقسام
        ctx["active_id"] = None
        ctx["editable_ids"] = []   # لاحقًا تضيف صلاحيات التحرير إن أردت

        return ctx


class DepartmentDetailView(DetailView):
    model = Department
    template_name = "hr/department_detail.html"
    context_object_name = "department"

    def dispatch(self, request, *args, **kwargs):
        dept = self.get_object()
        if not can_view_department(request.user, dept):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        dept = self.object

        # Children (sub-departments)
        ctx["children"] = dept.children_list

        # Employees inside this department
        ctx["employees"] = Employee.objects.filter(
            department_id=dept.id,
            company_id=dept.company_id
        ).select_related("job", "manager")

        # Department path (for breadcrumb)
        ctx["ancestors"] = dept.get_ancestors()

        return ctx


class DepartmentCreateView(CreateView):
    model = Department
    form_class = DepartmentForm
    template_name = "hr/department_form.html"
    success_url = reverse_lazy("hr:department_list")


class DepartmentUpdateView(UpdateView):
    model = Department
    form_class = DepartmentForm
    template_name = "hr/department_form.html"
    success_url = reverse_lazy("hr:department_list")

    def dispatch(self, request, *args, **kwargs):
        dept = self.get_object()
        if not can_edit_department(request.user, dept):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


# ============================================================
# Employees
# ============================================================

class EmployeeListView(ListView):
    model = Employee
    template_name = "hr/employee_list.html"
    context_object_name = "employees"

    def get_queryset(self):
        user = self.request.user
        return Employee.objects.filter(
            company_id__in=user.company_ids
        ).select_related("department", "job", "manager")


class EmployeeDetailView(DetailView):
    model = Employee
    template_name = "hr/employee_detail.html"
    context_object_name = "employee"

    def dispatch(self, request, *args, **kwargs):
        emp = self.get_object()
        if not can_view_employee(request.user, emp):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        emp = self.object

        # Subordinates (direct)
        ctx["subordinates"] = emp.subordinates

        # Full chain of managers
        chain = []
        current = emp.manager
        while current:
            chain.append(current)
            current = current.manager
        ctx["manager_chain"] = chain

        return ctx


class EmployeeCreateView(CreateView):
    model = Employee
    form_class = EmployeeForm
    template_name = "hr/employee_form.html"
    success_url = reverse_lazy("hr:employee_list")


class EmployeeUpdateView(UpdateView):
    model = Employee
    form_class = EmployeeForm
    template_name = "hr/employee_form.html"
    success_url = reverse_lazy("hr:employee_list")

    def dispatch(self, request, *args, **kwargs):
        emp = self.get_object()
        if not can_edit_employee(request.user, emp):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


# ============================================================
# Jobs
# ============================================================

class JobListView(ListView):
    model = Job
    template_name = "hr/job_list.html"
    context_object_name = "jobs"

    def get_queryset(self):
        return Job.objects.filter(company_id__in=self.request.user.company_ids)


class JobDetailView(DetailView):
    model = Job
    template_name = "hr/job_detail.html"
    context_object_name = "job"


class JobCreateView(CreateView):
    model = Job
    form_class = JobForm
    template_name = "hr/job_form.html"
    success_url = reverse_lazy("hr:job_list")


class JobUpdateView(UpdateView):
    model = Job
    form_class = JobForm
    template_name = "hr/job_form.html"
    success_url = reverse_lazy("hr:job_list")
