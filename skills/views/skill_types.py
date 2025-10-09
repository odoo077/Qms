# skills/views/skill_types.py
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView
from django.db.models import Q

from skills.models import HrSkillType
from skills.forms import SkillTypeForm


class SkillTypeListView(LoginRequiredMixin, ListView):
    model = HrSkillType
    template_name = "skills/skill_types/skill_type_list.html"
    context_object_name = "types"
    paginate_by = 20
    ordering = ("sequence", "name")

    def get_queryset(self):
        qs = HrSkillType.objects.order_by(*self.ordering)
        q = self.request.GET.get("q")
        active = self.request.GET.get("active")
        if q:
            qs = qs.filter(Q(name__icontains=q))
        if active in {"true", "false"}:
            qs = qs.filter(active=(active == "true"))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = "Skill Types"
        return ctx


class SkillTypeCreateView(LoginRequiredMixin, CreateView):
    model = HrSkillType
    form_class = SkillTypeForm
    template_name = "skills/skill_types/skill_type_form.html"
    success_url = reverse_lazy("skills:skill_type_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = "Create Skill Type"
        return ctx


class SkillTypeUpdateView(LoginRequiredMixin, UpdateView):
    model = HrSkillType
    form_class = SkillTypeForm
    template_name = "skills/skill_types/skill_type_form.html"
    success_url = reverse_lazy("skills:skill_type_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = "Edit Skill Type"
        return ctx


class SkillTypeDetailView(LoginRequiredMixin, DetailView):
    model = HrSkillType
    template_name = "skills/skill_types/skill_type_detail.html"
    context_object_name = "stype"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        stype = self.object
        ctx["page_title"] = f"Skill Type: {stype.name}"
        return ctx


class SkillTypeDeleteView(LoginRequiredMixin, DeleteView):
    model = HrSkillType
    template_name = "skills/skill_types/skill_type_confirm_delete.html"
    success_url = reverse_lazy("skills:skill_type_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = "Delete Skill Type"
        return ctx
