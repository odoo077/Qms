# hr/views/work_locations.py
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView
from ..models import WorkLocation
from ..forms import WorkLocationForm

class WorkLocationListView(LoginRequiredMixin, ListView):
    model = WorkLocation
    template_name = "hr/work_locations/work_location_list.html"
    context_object_name = "locations"
    paginate_by = 20
    ordering = ("company__name", "name")

    def get_queryset(self):
        qs = WorkLocation.objects.select_related("company", "address").order_by(*self.ordering)
        q = self.request.GET.get("q")
        company = self.request.GET.get("company")
        active = self.request.GET.get("active")
        if q:
            qs = qs.filter(name__icontains=q) | qs.filter(location_number__icontains=q)
        if company:
            qs = qs.filter(company_id=company)
        if active in {"true", "false"}:
            qs = qs.filter(active=(active == "true"))
        return qs

class WorkLocationCreateView(LoginRequiredMixin, CreateView):
    model = WorkLocation
    form_class = WorkLocationForm
    template_name = "hr/work_locations/work_location_form.html"
    success_url = reverse_lazy("hr:work_location_list")

class WorkLocationUpdateView(LoginRequiredMixin, UpdateView):
    model = WorkLocation
    form_class = WorkLocationForm
    template_name = "hr/work_locations/work_location_form.html"
    success_url = reverse_lazy("hr:work_location_list")

class WorkLocationDetailView(LoginRequiredMixin, DetailView):
    model = WorkLocation
    template_name = "hr/work_locations/work_location_detail.html"
    context_object_name = "location"

class WorkLocationDeleteView(LoginRequiredMixin, DeleteView):
    model = WorkLocation
    template_name = "hr/work_locations/work_location_confirm_delete.html"
    success_url = reverse_lazy("hr:work_location_list")
