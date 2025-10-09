# hr/views/work_locations.py
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView
from django.db.models import Q
from django.apps import apps

from ..models import WorkLocation
from ..forms import WorkLocationForm


class WorkLocationListView(LoginRequiredMixin, ListView):
    """
    عرض قائمة مواقع العمل (Work Locations)
    يدعم البحث، الفلترة حسب الشركة والحالة (active)
    يعتمد على الحقل active من ActivableMixin.
    """
    model = WorkLocation
    template_name = "hr/work_locations/work_location_list.html"
    context_object_name = "locations"
    paginate_by = 20
    ordering = ("company__name", "name")

    def get_queryset(self):
        qs = (
            WorkLocation.objects
            .select_related("company", "address")
            .order_by(*self.ordering)
        )

        q = self.request.GET.get("q")
        company = self.request.GET.get("company")
        active = self.request.GET.get("active")

        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(location_number__icontains=q))
        if company:
            qs = qs.filter(company_id=company)
        if active in {"true", "false"}:
            qs = qs.filter(active=(active == "true"))

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        Company = apps.get_model("base", "Company")
        ctx["companies"] = Company.objects.order_by("name")
        ctx["page_title"] = "Work Locations"
        return ctx


class WorkLocationCreateView(LoginRequiredMixin, CreateView):
    """
    إنشاء موقع عمل جديد.
    """
    model = WorkLocation
    form_class = WorkLocationForm
    template_name = "hr/work_locations/work_location_form.html"
    success_url = reverse_lazy("hr:work_location_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = "Create Work Location"
        return ctx


class WorkLocationUpdateView(LoginRequiredMixin, UpdateView):
    """
    تعديل موقع عمل موجود.
    """
    model = WorkLocation
    form_class = WorkLocationForm
    template_name = "hr/work_locations/work_location_form.html"
    success_url = reverse_lazy("hr:work_location_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = "Edit Work Location"
        return ctx


class WorkLocationDetailView(LoginRequiredMixin, DetailView):
    """
    عرض تفاصيل موقع العمل.
    """
    model = WorkLocation
    template_name = "hr/work_locations/work_location_detail.html"
    context_object_name = "location"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        location = self.object
        ctx["page_title"] = f"Work Location: {location.name}"
        return ctx


class WorkLocationDeleteView(LoginRequiredMixin, DeleteView):
    """
    حذف موقع عمل.
    """
    model = WorkLocation
    template_name = "hr/work_locations/work_location_confirm_delete.html"
    success_url = reverse_lazy("hr:work_location_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = "Delete Work Location"
        return ctx
