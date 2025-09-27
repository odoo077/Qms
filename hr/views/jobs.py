# hr/views/jobs.py
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView
from ..models import Job
from ..forms import JobForm

class JobListView(LoginRequiredMixin, ListView):
    model = Job
    template_name = "hr/jobs/job_list.html"
    context_object_name = "jobs"
    paginate_by = 20
    ordering = ("company__name", "department__complete_name", "name")

    def get_queryset(self):
        qs = (Job.objects
              .select_related("company", "department", "recruiter", "contract_type")
              .order_by(*self.ordering))
        q = self.request.GET.get("q")
        dept = self.request.GET.get("department")
        company = self.request.GET.get("company")
        active = self.request.GET.get("active")
        if q:
            qs = qs.filter(name__icontains=q)
        if dept:
            qs = qs.filter(department_id=dept)
        if company:
            qs = qs.filter(company_id=company)
        if active in {"true", "false"}:
            qs = qs.filter(active=(active == "true"))
        return qs

class JobCreateView(LoginRequiredMixin, CreateView):
    model = Job
    form_class = JobForm
    template_name = "hr/jobs/job_form.html"
    success_url = reverse_lazy("hr:job_list")

class JobUpdateView(LoginRequiredMixin, UpdateView):
    model = Job
    form_class = JobForm
    template_name = "hr/jobs/job_form.html"
    success_url = reverse_lazy("hr:job_list")

class JobDetailView(LoginRequiredMixin, DetailView):
    model = Job
    template_name = "hr/jobs/job_detail.html"
    context_object_name = "job"

class JobDeleteView(LoginRequiredMixin, DeleteView):
    model = Job
    template_name = "hr/jobs/job_confirm_delete.html"
    success_url = reverse_lazy("hr:job_list")
