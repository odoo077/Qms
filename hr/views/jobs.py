# hr/views/jobs.py
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView
from django.db.models import Q
from django.apps import apps

from ..models import Job
from ..forms import JobForm


class JobListView(LoginRequiredMixin, ListView):
    """
    عرض قائمة الوظائف (Jobs) مع فلاتر البحث والشركة والقسم والحالة.
    يعتمد على الحقل active من ActivableMixin.
    """
    model = Job
    template_name = "hr/jobs/job_list.html"
    context_object_name = "jobs"
    paginate_by = 20
    ordering = ("company__name", "department__complete_name", "name")

    def get_queryset(self):
        qs = (
            Job.objects
            .select_related("company", "department", "recruiter", "contract_type")
            .order_by(*self.ordering)
        )

        q = self.request.GET.get("q")
        dept = self.request.GET.get("department")
        company = self.request.GET.get("company")
        active = self.request.GET.get("active")

        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q))
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
        Department = apps.get_model("hr", "Department")
        ctx["companies"] = Company.objects.order_by("name")
        ctx["departments"] = Department.objects.select_related("company").order_by("complete_name")
        ctx["page_title"] = "Jobs"
        return ctx


class JobCreateView(LoginRequiredMixin, CreateView):
    """
    إنشاء وظيفة جديدة.
    """
    model = Job
    form_class = JobForm
    template_name = "hr/jobs/job_form.html"
    success_url = reverse_lazy("hr:job_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = "Create Job"
        return ctx


class JobUpdateView(LoginRequiredMixin, UpdateView):
    """
    تعديل وظيفة موجودة.
    """
    model = Job
    form_class = JobForm
    template_name = "hr/jobs/job_form.html"
    success_url = reverse_lazy("hr:job_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = "Edit Job"
        return ctx


class JobDetailView(LoginRequiredMixin, DetailView):
    """
    عرض تفاصيل الوظيفة (Job)
    """
    model = Job
    template_name = "hr/jobs/job_detail.html"
    context_object_name = "job"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        job = self.object
        ctx["page_title"] = f"Job: {job.name}"
        ctx["employee_count"] = job.no_of_employee
        ctx["expected_employees"] = job.expected_employees
        return ctx


class JobDeleteView(LoginRequiredMixin, DeleteView):
    """
    حذف وظيفة.
    """
    model = Job
    template_name = "hr/jobs/job_confirm_delete.html"
    success_url = reverse_lazy("hr:job_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = "Delete Job"
        return ctx
