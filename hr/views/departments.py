# hr/views/departments.py
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView
from django.apps import apps
from django.db.models import Q

from ..models import Department
from ..forms import DepartmentForm


class DepartmentListView(LoginRequiredMixin, ListView):
    """
    عرض قائمة الأقسام مع دعم البحث والفلاتر (الشركة / الحالة)
    - يعرض member_count (بدل total_employee)
    - يعتمد على الحقل active من ActivableMixin
    """
    model = Department
    template_name = "hr/departments/department_list.html"
    context_object_name = "departments"
    paginate_by = 20
    ordering = ("company__name", "complete_name")

    def get_queryset(self):
        qs = (
            Department.objects
            .select_related("company", "parent", "manager")
            .order_by(*self.ordering)
        )

        q = self.request.GET.get("q")
        company = self.request.GET.get("company")
        active = self.request.GET.get("active")

        if q:
            qs = qs.filter(Q(complete_name__icontains=q) | Q(name__icontains=q))
        if company:
            qs = qs.filter(company_id=company)
        if active in {"true", "false"}:
            qs = qs.filter(active=(active == "true"))

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        Company = apps.get_model("base", "Company")
        ctx["companies"] = Company.objects.order_by("name")
        ctx["page_title"] = "Departments"
        return ctx


class DepartmentCreateView(LoginRequiredMixin, CreateView):
    """
    إنشاء قسم جديد
    """
    model = Department
    form_class = DepartmentForm
    template_name = "hr/departments/department_form.html"
    success_url = reverse_lazy("hr:department_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = "Create Department"
        return ctx


class DepartmentUpdateView(LoginRequiredMixin, UpdateView):
    """
    تعديل قسم موجود
    """
    model = Department
    form_class = DepartmentForm
    template_name = "hr/departments/department_form.html"
    success_url = reverse_lazy("hr:department_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = "Edit Department"
        return ctx


class DepartmentDetailView(LoginRequiredMixin, DetailView):
    """
    عرض تفاصيل القسم
    - يعرض member_count كمحتسب
    """
    model = Department
    template_name = "hr/departments/department_detail.html"
    context_object_name = "department"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        department = self.object
        ctx["page_title"] = f"Department: {department.name}"
        ctx["member_count"] = department.member_count  # يعرض العدد المحسوب بدلاً من total_employee
        return ctx


class DepartmentDeleteView(LoginRequiredMixin, DeleteView):
    """
    حذف قسم
    """
    model = Department
    template_name = "hr/departments/department_confirm_delete.html"
    success_url = reverse_lazy("hr:department_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = "Delete Department"
        return ctx
