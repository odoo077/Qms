# skills/views/skills.py
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView
from django.db.models import Q
from skills.models import HrSkillType
from skills.models import HrSkill
from skills.forms import SkillForm


class SkillListView(LoginRequiredMixin, ListView):
    model = HrSkill
    template_name = "skills/skills/skill_list.html"
    context_object_name = "skills"
    paginate_by = 20
    ordering = ("skill_type__name", "sequence", "name")

    def get_queryset(self):
        qs = (HrSkill.objects
              .select_related("skill_type")
              .order_by(*self.ordering))
        q = self.request.GET.get("q")
        st = self.request.GET.get("skill_type")
        active = self.request.GET.get("active")
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(skill_type__name__icontains=q))
        if st:
            qs = qs.filter(skill_type_id=st)
        if active in {"true", "false"}:
            qs = qs.filter(active=(active == "true"))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = "Skills"
        ctx["skill_types"] = HrSkillType.objects.order_by("name")
        return ctx


class SkillCreateView(LoginRequiredMixin, CreateView):
    model = HrSkill
    form_class = SkillForm
    template_name = "skills/skills/skill_form.html"
    success_url = reverse_lazy("skills:skill_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = "Create Skill"
        return ctx


class SkillUpdateView(LoginRequiredMixin, UpdateView):
    model = HrSkill
    form_class = SkillForm
    template_name = "skills/skills/skill_form.html"
    success_url = reverse_lazy("skills:skill_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = "Edit Skill"
        return ctx


class SkillDetailView(LoginRequiredMixin, DetailView):
    model = HrSkill
    template_name = "skills/skills/skill_detail.html"
    context_object_name = "skill"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        skill = self.object
        ctx["page_title"] = f"Skill: {skill.name}"
        return ctx


class SkillDeleteView(LoginRequiredMixin, DeleteView):
    model = HrSkill
    template_name = "skills/skills/skill_confirm_delete.html"
    success_url = reverse_lazy("skills:skill_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = "Delete Skill"
        return ctx
