# hr/views/departments.py
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView
from ..models import Department
from ..forms import DepartmentForm
from django.apps import apps

class DepartmentListView(LoginRequiredMixin, ListView):
    model = Department
    template_name = "hr/departments/department_list.html"
    context_object_name = "departments"
    paginate_by = 20
    ordering = ("company__name", "complete_name")

    def get_queryset(self):
        qs = (Department.objects
              .select_related("company", "parent", "manager")
              .order_by(*self.ordering))
        q = self.request.GET.get("q")
        company = self.request.GET.get("company")
        active = self.request.GET.get("active")
        if q:
            qs = qs.filter(complete_name__icontains=q) | qs.filter(name__icontains=q)
        if company:
            qs = qs.filter(company_id=company)
        if active in {"true", "false"}:
            qs = qs.filter(active=(active == "true"))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        Company = apps.get_model("base", "Company")
        ctx["companies"] = Company.objects.order_by("name")
        return ctx


class DepartmentCreateView(LoginRequiredMixin, CreateView):
    model = Department
    form_class = DepartmentForm
    template_name = "hr/departments/department_form.html"
    success_url = reverse_lazy("hr:department_list")

class DepartmentUpdateView(LoginRequiredMixin, UpdateView):
    model = Department
    form_class = DepartmentForm
    template_name = "hr/departments/department_form.html"
    success_url = reverse_lazy("hr:department_list")

class DepartmentDetailView(LoginRequiredMixin, DetailView):
    model = Department
    template_name = "hr/departments/department_detail.html"
    context_object_name = "department"

class DepartmentDeleteView(LoginRequiredMixin, DeleteView):
    model = Department
    template_name = "hr/departments/department_confirm_delete.html"
    success_url = reverse_lazy("hr:department_list")
