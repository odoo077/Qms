# hr/views/employees.py
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.db.models import Q
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView
from django.apps import apps

from ..models import Employee, Department
from ..forms import EmployeeForm


class EmployeeListView(LoginRequiredMixin, ListView):
    """
    عرض قائمة الموظفين (Employees)
    يدعم البحث والفلاتر حسب القسم، الشركة، الحالة (active)
    ويعرض بيانات الاتصال والعمل.
    """
    model = Employee
    template_name = "hr/employees/employee_list.html"
    context_object_name = "employees"
    paginate_by = 20
    ordering = ("company__name", "name")

    def get_queryset(self):
        qs = (
            Employee.objects
            .select_related(
                "company",
                "department",
                "job",
                "manager",
                "coach",
                "work_location",
                "work_contact",
                "address_home",   # تمت إضافته بعد تحديث الموديل
            )
            .order_by(*self.ordering)
        )

        q = self.request.GET.get("q")
        dept = self.request.GET.get("department")
        company = self.request.GET.get("company")
        active = self.request.GET.get("active")

        # البحث النصي العام
        if q:
            qs = qs.filter(
                Q(name__icontains=q)
                | Q(work_email__icontains=q)
                | Q(private_email__icontains=q)
                | Q(work_phone__icontains=q)
                | Q(mobile_phone__icontains=q)
                | Q(private_phone__icontains=q)
                | Q(work_contact__display_name__icontains=q)
            )

        # الفلاتر
        if dept:
            qs = qs.filter(department_id=dept)
        if company:
            qs = qs.filter(company_id=company)
        if active in {"true", "false"}:
            qs = qs.filter(active=(active == "true"))

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        Company = apps.get_model("base", "Company")
        ctx["companies"] = Company.objects.order_by("name")
        ctx["departments"] = Department.objects.select_related("company").order_by("company__name", "complete_name")
        ctx["page_title"] = "Employees"
        return ctx


class EmployeeCreateView(LoginRequiredMixin, CreateView):
    """
    إنشاء موظف جديد.
    """
    model = Employee
    form_class = EmployeeForm
    template_name = "hr/employees/employee_form.html"
    success_url = reverse_lazy("hr:employee_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = "Create Employee"
        return ctx


class EmployeeUpdateView(LoginRequiredMixin, UpdateView):
    """
    تعديل بيانات موظف موجود.
    """
    model = Employee
    form_class = EmployeeForm
    template_name = "hr/employees/employee_form.html"
    success_url = reverse_lazy("hr:employee_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = "Edit Employee"
        return ctx


class EmployeeDetailView(LoginRequiredMixin, DetailView):
    """
    عرض تفاصيل الموظف (Employee Detail)
    """
    model = Employee
    template_name = "hr/employees/employee_detail.html"
    context_object_name = "employee"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        employee = self.object
        ctx["page_title"] = f"Employee: {employee.name}"

        # تمرير البيانات الإضافية للعرض (تمامًا مثل Odoo)
        ctx["address_home"] = employee.address_home
        ctx["marital_status"] = employee.marital_status
        ctx["gender"] = employee.gender
        ctx["children"] = employee.children
        ctx["identification_id"] = employee.identification_id
        ctx["passport_id"] = employee.passport_id
        ctx["bank_account"] = employee.bank_account
        ctx["car"] = employee.car

        return ctx


class EmployeeDeleteView(LoginRequiredMixin, DeleteView):
    """
    حذف موظف.
    """
    model = Employee
    template_name = "hr/employees/employee_confirm_delete.html"
    success_url = reverse_lazy("hr:employee_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = "Delete Employee"
        return ctx
