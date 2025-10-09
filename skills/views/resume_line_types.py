# skills/views/resume_line_types.py
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView
from django.db.models import Q

from skills.models import HrResumeLineType
from skills.forms import ResumeLineTypeForm


class ResumeLineTypeListView(LoginRequiredMixin, ListView):
    model = HrResumeLineType
    template_name = "skills/resume_line_types/resume_line_type_list.html"
    context_object_name = "types"
    paginate_by = 20
    ordering = ("sequence", "name")

    def get_queryset(self):
        qs = HrResumeLineType.objects.order_by(*self.ordering)
        q = self.request.GET.get("q")
        active = self.request.GET.get("active")
        if q:
            qs = qs.filter(Q(name__icontains=q))
        if active in {"true", "false"}:
            qs = qs.filter(active=(active == "true"))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = "Resume Line Types"
        return ctx


class ResumeLineTypeCreateView(LoginRequiredMixin, CreateView):
    model = HrResumeLineType
    form_class = ResumeLineTypeForm
    template_name = "skills/resume_line_types/resume_line_type_form.html"
    success_url = reverse_lazy("skills:resume_line_type_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = "Create Resume Line Type"
        return ctx


class ResumeLineTypeUpdateView(LoginRequiredMixin, UpdateView):
    model = HrResumeLineType
    form_class = ResumeLineTypeForm
    template_name = "skills/resume_line_types/resume_line_type_form.html"
    success_url = reverse_lazy("skills:resume_line_type_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = "Edit Resume Line Type"
        return ctx


class ResumeLineTypeDetailView(LoginRequiredMixin, DetailView):
    model = HrResumeLineType
    template_name = "skills/resume_line_types/resume_line_type_detail.html"
    context_object_name = "rtype"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        rtype = self.object
        ctx["page_title"] = f"Resume Line Type: {rtype.name}"
        return ctx


class ResumeLineTypeDeleteView(LoginRequiredMixin, DeleteView):
    model = HrResumeLineType
    template_name = "skills/resume_line_types/resume_line_type_confirm_delete.html"
    success_url = reverse_lazy("skills:resume_line_type_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = "Delete Resume Line Type"
        return ctx
