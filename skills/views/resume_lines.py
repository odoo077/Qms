# skills/views/resume_lines.py
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView
from django.db.models import Q
from django.apps import apps

from skills.models import HrResumeLine
from skills.forms import ResumeLineForm


class ResumeLineListView(LoginRequiredMixin, ListView):
    model = HrResumeLine
    template_name = "skills/resume_lines/resume_line_list.html"
    context_object_name = "lines"
    paginate_by = 20
    ordering = ("-date_start", "-date_end", "id")

    def get_queryset(self):
        qs = (HrResumeLine.objects
              .select_related("employee", "line_type", "company", "department")
              .order_by(*self.ordering))
        q = self.request.GET.get("q")
        emp = self.request.GET.get("employee")
        rtype = self.request.GET.get("line_type")
        if q:
            qs = qs.filter(
                Q(name__icontains=q)
                | Q(employee__name__icontains=q)
                | Q(line_type__name__icontains=q)
            )
        if emp:
            qs = qs.filter(employee_id=emp)
        if rtype:
            qs = qs.filter(line_type_id=rtype)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        Employee = apps.get_model("hr", "Employee")
        from skills.models import HrResumeLineType
        ctx["employees"] = Employee.objects.order_by("name")
        ctx["line_types"] = HrResumeLineType.objects.order_by("sequence", "name")
        ctx["page_title"] = "Resume Lines"
        return ctx


class ResumeLineCreateView(LoginRequiredMixin, CreateView):
    model = HrResumeLine
    form_class = ResumeLineForm
    template_name = "skills/resume_lines/resume_line_form.html"
    success_url = reverse_lazy("skills:resume_line_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = "Create Resume Line"
        return ctx


class ResumeLineUpdateView(LoginRequiredMixin, UpdateView):
    model = HrResumeLine
    form_class = ResumeLineForm
    template_name = "skills/resume_lines/resume_line_form.html"
    success_url = reverse_lazy("skills:resume_line_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = "Edit Resume Line"
        return ctx


class ResumeLineDetailView(LoginRequiredMixin, DetailView):
    model = HrResumeLine
    template_name = "skills/resume_lines/resume_line_detail.html"
    context_object_name = "line"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        line = self.object
        ctx["page_title"] = f"Resume Line: {line.name}"
        return ctx


class ResumeLineDeleteView(LoginRequiredMixin, DeleteView):
    model = HrResumeLine
    template_name = "skills/resume_lines/resume_line_confirm_delete.html"
    success_url = reverse_lazy("skills:resume_line_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = "Delete Resume Line"
        return ctx
