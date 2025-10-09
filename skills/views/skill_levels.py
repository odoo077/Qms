# skills/views/skill_levels.py
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView
from django.db.models import Q
from django.apps import apps

from skills.models import HrSkillLevel
from skills.forms import SkillLevelForm


class SkillLevelListView(LoginRequiredMixin, ListView):
    model = HrSkillLevel
    template_name = "skills/skill_levels/skill_level_list.html"
    context_object_name = "levels"
    paginate_by = 20
    ordering = ("skill_type__name", "level_progress", "id")

    def get_queryset(self):
        qs = (HrSkillLevel.objects
              .select_related("skill_type")
              .order_by(*self.ordering))
        q = self.request.GET.get("q")
        st = self.request.GET.get("skill_type")
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(skill_type__name__icontains=q))
        if st:
            qs = qs.filter(skill_type_id=st)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = "Skill Levels"
        return ctx


class SkillLevelCreateView(LoginRequiredMixin, CreateView):
    model = HrSkillLevel
    form_class = SkillLevelForm
    template_name = "skills/skill_levels/skill_level_form.html"
    success_url = reverse_lazy("skills:skill_level_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = "Create Skill Level"
        return ctx


class SkillLevelUpdateView(LoginRequiredMixin, UpdateView):
    model = HrSkillLevel
    form_class = SkillLevelForm
    template_name = "skills/skill_levels/skill_level_form.html"
    success_url = reverse_lazy("skills:skill_level_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = "Edit Skill Level"
        return ctx


class SkillLevelDetailView(LoginRequiredMixin, DetailView):
    model = HrSkillLevel
    template_name = "skills/skill_levels/skill_level_detail.html"
    context_object_name = "level"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        level = self.object
        ctx["page_title"] = f"Skill Level: {level.name}"
        return ctx


class SkillLevelDeleteView(LoginRequiredMixin, DeleteView):
    model = HrSkillLevel
    template_name = "skills/skill_levels/skill_level_confirm_delete.html"
    success_url = reverse_lazy("skills:skill_level_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = "Delete Skill Level"
        return ctx
