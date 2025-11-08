# skills/views.py
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from base.views import BaseScopedListView, apply_search_filters
from .models import SkillType, SkillLevel, Skill, EmployeeSkill, ResumeLine, ResumeLineType
from .forms import (
    SkillTypeForm, SkillLevelForm, SkillForm,
    EmployeeSkillForm, ResumeLineTypeForm, ResumeLineForm
)

# ------------------------------------------
# SkillType
# ------------------------------------------
class SkillTypeListView(LoginRequiredMixin, BaseScopedListView):
    model = SkillType
    template_name = "skills/skilltype_list.html"
    paginate_by = 24

    def get_queryset(self):
        qs = SkillType.objects.all().order_by("sequence", "name")
        return apply_search_filters(self.request, qs, search_fields=["name"])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_add_skilltype"] = self.request.user.has_perm("skills.add_skilltype")
        return ctx


class SkillTypeCreateView(LoginRequiredMixin, BaseScopedListView):
    model = SkillType
    form_class = SkillTypeForm
    template_name = "skills/skilltype_form.html"
    success_url = reverse_lazy("skills:skilltype_list")


class SkillTypeUpdateView(LoginRequiredMixin, BaseScopedListView):
    model = SkillType
    form_class = SkillTypeForm
    template_name = "skills/skilltype_form.html"
    success_url = reverse_lazy("skills:skilltype_list")


# ------------------------------------------
# SkillLevel
# ------------------------------------------
class SkillLevelListView(LoginRequiredMixin, BaseScopedListView):
    model = SkillLevel
    template_name = "skills/skilllevel_list.html"
    paginate_by = 24

    def get_queryset(self):
        qs = SkillLevel.objects.select_related("skill_type").order_by("skill_type__sequence", "level_progress")
        return apply_search_filters(self.request, qs, search_fields=["name", "skill_type__name"])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_add_skilllevel"] = self.request.user.has_perm("skills.add_skilllevel")
        return ctx


class SkillLevelCreateView(LoginRequiredMixin, BaseScopedListView):
    model = SkillLevel
    form_class = SkillLevelForm
    template_name = "skills/skilllevel_form.html"
    success_url = reverse_lazy("skills:skilllevel_list")


class SkillLevelUpdateView(LoginRequiredMixin, BaseScopedListView):
    model = SkillLevel
    form_class = SkillLevelForm
    template_name = "skills/skilllevel_form.html"
    success_url = reverse_lazy("skills:skilllevel_list")


# ------------------------------------------
# Skill
# ------------------------------------------
class SkillListView(LoginRequiredMixin, BaseScopedListView):
    model = Skill
    template_name = "skills/skill_list.html"
    paginate_by = 24

    def get_queryset(self):
        qs = Skill.objects.select_related("skill_type").order_by("skill_type__sequence", "name")
        return apply_search_filters(self.request, qs, search_fields=["name", "skill_type__name"])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_add_skill"] = self.request.user.has_perm("skills.add_skill")
        return ctx


class SkillCreateView(LoginRequiredMixin, BaseScopedListView):
    model = Skill
    form_class = SkillForm
    template_name = "skills/skill_form.html"
    success_url = reverse_lazy("skills:skill_list")


class SkillUpdateView(LoginRequiredMixin, BaseScopedListView):
    model = Skill
    form_class = SkillForm
    template_name = "skills/skill_form.html"
    success_url = reverse_lazy("skills:skill_list")


# ------------------------------------------
# EmployeeSkill
# ------------------------------------------
class EmployeeSkillListView(LoginRequiredMixin, BaseScopedListView):
    model = EmployeeSkill
    template_name = "skills/employeeskill_list.html"
    paginate_by = 24

    def get_queryset(self):
        qs = EmployeeSkill.objects.select_related("employee", "skill_type", "skill", "skill_level").order_by("employee__name")
        return apply_search_filters(self.request, qs, search_fields=["employee__name", "skill__name", "skill_type__name"])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_add_employeeskill"] = self.request.user.has_perm("skills.add_employeeskill")
        return ctx


class EmployeeSkillCreateView(LoginRequiredMixin, BaseScopedListView):
    model = EmployeeSkill
    form_class = EmployeeSkillForm
    template_name = "skills/employeeskill_form.html"
    success_url = reverse_lazy("skills:employeeskill_list")


class EmployeeSkillUpdateView(LoginRequiredMixin, BaseScopedListView):
    model = EmployeeSkill
    form_class = EmployeeSkillForm
    template_name = "skills/employeeskill_form.html"
    success_url = reverse_lazy("skills:employeeskill_list")


# ------------------------------------------
# ResumeLineType
# ------------------------------------------
class ResumeLineTypeListView(LoginRequiredMixin, BaseScopedListView):
    model = ResumeLineType
    template_name = "skills/resumelinetype_list.html"
    paginate_by = 24

    def get_queryset(self):
        qs = ResumeLineType.objects.order_by("sequence", "name")
        return apply_search_filters(self.request, qs, search_fields=["name"])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_add_resumelinetype"] = self.request.user.has_perm("skills.add_resumelinetype")
        return ctx


class ResumeLineTypeCreateView(LoginRequiredMixin, BaseScopedListView):
    model = ResumeLineType
    form_class = ResumeLineTypeForm
    template_name = "skills/resumelinetype_form.html"
    success_url = reverse_lazy("skills:resumelinetype_list")


class ResumeLineTypeUpdateView(LoginRequiredMixin, BaseScopedListView):
    model = ResumeLineType
    form_class = ResumeLineTypeForm
    template_name = "skills/resumelinetype_form.html"
    success_url = reverse_lazy("skills:resumelinetype_list")


# ------------------------------------------
# ResumeLine
# ------------------------------------------
class ResumeLineListView(LoginRequiredMixin, BaseScopedListView):
    model = ResumeLine
    template_name = "skills/resumeline_list.html"
    paginate_by = 24

    def get_queryset(self):
        qs = ResumeLine.objects.select_related("employee", "line_type").order_by("employee__name")
        return apply_search_filters(self.request, qs, search_fields=["name", "employee__name", "line_type__name"])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_add_resumeline"] = self.request.user.has_perm("skills.add_resumeline")
        return ctx


class ResumeLineCreateView(LoginRequiredMixin, BaseScopedListView):
    model = ResumeLine
    form_class = ResumeLineForm
    template_name = "skills/resumeline_form.html"
    success_url = reverse_lazy("skills:resumeline_list")


class ResumeLineUpdateView(LoginRequiredMixin, BaseScopedListView):
    model = ResumeLine
    form_class = ResumeLineForm
    template_name = "skills/resumeline_form.html"
    success_url = reverse_lazy("skills:resumeline_list")
