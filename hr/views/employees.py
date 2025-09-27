# hr/views/employees.py
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.db.models import Q, Prefetch
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView
from ..models import Employee, Department
from ..forms import EmployeeForm
from django.apps import apps

class EmployeeListView(LoginRequiredMixin, ListView):
    model = Employee
    template_name = "hr/employees/employee_list.html"
    context_object_name = "employees"
    paginate_by = 20

    def get_queryset(self):
        qs = (
            Employee.objects
            .select_related("company", "department", "job", "manager", "coach", "work_location", "work_contact")
            .order_by("company__name", "name")
        )
        q = self.request.GET.get("q")
        dept = self.request.GET.get("department")
        company = self.request.GET.get("company")
        active = self.request.GET.get("active")

        if q:
            qs = qs.filter(
                Q(name__icontains=q) |
                Q(work_email__icontains=q) |
                Q(work_phone__icontains=q) |
                Q(mobile_phone__icontains=q) |
                Q(work_contact__display_name__icontains=q)
            )

        if dept:
            qs = qs.filter(department_id=dept)
        if company:
            qs = qs.filter(company_id=company)
        if active in {"true", "false"}:
            qs = qs.filter(active=(active == "true"))

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["departments"] = Department.objects.select_related("company").order_by("company__name", "complete_name")

        # NEW: مرّر قائمة الشركات للفلترة في التمبلت
        Company = apps.get_model("base", "Company")
        ctx["companies"] = Company.objects.order_by("name")
        return ctx


class EmployeeCreateView(LoginRequiredMixin, CreateView):
    model = Employee
    form_class = EmployeeForm
    template_name = "hr/employees/employee_form.html"
    success_url = reverse_lazy("hr:employee_list")


class EmployeeUpdateView(LoginRequiredMixin, UpdateView):
    model = Employee
    form_class = EmployeeForm
    template_name = "hr/employees/employee_form.html"
    success_url = reverse_lazy("hr:employee_list")


class EmployeeDetailView(LoginRequiredMixin, DetailView):
    model = Employee
    template_name = "hr/employees/employee_detail.html"
    context_object_name = "employee"


class EmployeeDeleteView(LoginRequiredMixin, DeleteView):
    model = Employee
    template_name = "hr/employees/employee_confirm_delete.html"
    success_url = reverse_lazy("hr:employee_list")
