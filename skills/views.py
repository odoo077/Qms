# skills/views.py
# ============================================================
# Skills Views – SIMPLE MODE (NO ACL / NO BASE SCOPED)
# Django permissions only
# ============================================================

from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import (
    ListView,
    CreateView,
    UpdateView,
    DeleteView,
)

from .models import (
    SkillType,
    SkillLevel,
    Skill,
    EmployeeSkill,
    ResumeLineType,
    ResumeLine,
)

from .forms import (
    SkillTypeForm,
    SkillLevelForm,
    SkillForm,
    EmployeeSkillForm,
    ResumeLineTypeForm,
    ResumeLineForm,
)

# ============================================================
# Skill Type
# ============================================================

class SkillTypeListView(LoginRequiredMixin, ListView):
    model = SkillType
    template_name = "skills/skilltype_list.html"
    paginate_by = 25
    ordering = ["sequence", "name"]


class SkillTypeCreateView(LoginRequiredMixin, CreateView):
    model = SkillType
    form_class = SkillTypeForm
    template_name = "skills/skilltype_form.html"
    success_url = reverse_lazy("skills:skilltype_list")


class SkillTypeUpdateView(LoginRequiredMixin, UpdateView):
    model = SkillType
    form_class = SkillTypeForm
    template_name = "skills/skilltype_form.html"
    success_url = reverse_lazy("skills:skilltype_list")


class SkillTypeDeleteView(LoginRequiredMixin, DeleteView):
    model = SkillType
    template_name = "common/confirm_delete.html"
    success_url = reverse_lazy("skills:skilltype_list")


# ============================================================
# Skill Level
# ============================================================

class SkillLevelListView(LoginRequiredMixin, ListView):
    model = SkillLevel
    template_name = "skills/skilllevel_list.html"
    paginate_by = 25

    def get_queryset(self):
        return SkillLevel.objects.select_related("skill_type").order_by(
            "skill_type__sequence", "level_progress"
        )


class SkillLevelCreateView(LoginRequiredMixin, CreateView):
    model = SkillLevel
    form_class = SkillLevelForm
    template_name = "skills/skilllevel_form.html"
    success_url = reverse_lazy("skills:skilllevel_list")


class SkillLevelUpdateView(LoginRequiredMixin, UpdateView):
    model = SkillLevel
    form_class = SkillLevelForm
    template_name = "skills/skilllevel_form.html"
    success_url = reverse_lazy("skills:skilllevel_list")


class SkillLevelDeleteView(LoginRequiredMixin, DeleteView):
    model = SkillLevel
    template_name = "common/confirm_delete.html"
    success_url = reverse_lazy("skills:skilllevel_list")


# ============================================================
# Skill
# ============================================================

class SkillListView(LoginRequiredMixin, ListView):
    model = Skill
    template_name = "skills/skill_list.html"
    paginate_by = 25

    def get_queryset(self):
        return Skill.objects.select_related("skill_type").order_by(
            "skill_type__sequence", "name"
        )


class SkillCreateView(LoginRequiredMixin, CreateView):
    model = Skill
    form_class = SkillForm
    template_name = "skills/skill_form.html"
    success_url = reverse_lazy("skills:skill_list")


class SkillUpdateView(LoginRequiredMixin, UpdateView):
    model = Skill
    form_class = SkillForm
    template_name = "skills/skill_form.html"
    success_url = reverse_lazy("skills:skill_list")


class SkillDeleteView(LoginRequiredMixin, DeleteView):
    model = Skill
    template_name = "common/confirm_delete.html"
    success_url = reverse_lazy("skills:skill_list")


# ============================================================
# Employee Skill
# ============================================================

class EmployeeSkillListView(LoginRequiredMixin, ListView):
    model = EmployeeSkill
    template_name = "skills/employeeskill_list.html"
    paginate_by = 25

    def get_queryset(self):
        return EmployeeSkill.objects.select_related(
            "employee", "skill_type", "skill", "skill_level"
        ).order_by("employee__name")


class EmployeeSkillCreateView(LoginRequiredMixin, CreateView):
    model = EmployeeSkill
    form_class = EmployeeSkillForm
    template_name = "skills/employeeskill_form.html"
    success_url = reverse_lazy("skills:employeeskill_list")


class EmployeeSkillUpdateView(LoginRequiredMixin, UpdateView):
    model = EmployeeSkill
    form_class = EmployeeSkillForm
    template_name = "skills/employeeskill_form.html"
    success_url = reverse_lazy("skills:employeeskill_list")


class EmployeeSkillDeleteView(LoginRequiredMixin, DeleteView):
    model = EmployeeSkill
    template_name = "common/confirm_delete.html"
    success_url = reverse_lazy("skills:employeeskill_list")


# ============================================================
# Resume Line Type
# ============================================================

class ResumeLineTypeListView(LoginRequiredMixin, ListView):
    model = ResumeLineType
    template_name = "skills/resumelinetype_list.html"
    paginate_by = 25
    ordering = ["sequence", "name"]


class ResumeLineTypeCreateView(LoginRequiredMixin, CreateView):
    model = ResumeLineType
    form_class = ResumeLineTypeForm
    template_name = "skills/resumelinetype_form.html"
    success_url = reverse_lazy("skills:resumelinetype_list")


class ResumeLineTypeUpdateView(LoginRequiredMixin, UpdateView):
    model = ResumeLineType
    form_class = ResumeLineTypeForm
    template_name = "skills/resumelinetype_form.html"
    success_url = reverse_lazy("skills:resumelinetype_list")


class ResumeLineTypeDeleteView(LoginRequiredMixin, DeleteView):
    model = ResumeLineType
    template_name = "common/confirm_delete.html"
    success_url = reverse_lazy("skills:resumelinetype_list")


# ============================================================
# Resume Line
# ============================================================

class ResumeLineListView(LoginRequiredMixin, ListView):
    model = ResumeLine
    template_name = "skills/resumeline_list.html"
    paginate_by = 25

    def get_queryset(self):
        return ResumeLine.objects.select_related(
            "employee", "line_type"
        ).order_by("employee__name")


class ResumeLineCreateView(LoginRequiredMixin, CreateView):
    model = ResumeLine
    form_class = ResumeLineForm
    template_name = "skills/resumeline_form.html"
    success_url = reverse_lazy("skills:resumeline_list")


class ResumeLineUpdateView(LoginRequiredMixin, UpdateView):
    model = ResumeLine
    form_class = ResumeLineForm
    template_name = "skills/resumeline_form.html"
    success_url = reverse_lazy("skills:resumeline_list")


class ResumeLineDeleteView(LoginRequiredMixin, DeleteView):
    model = ResumeLine
    template_name = "common/confirm_delete.html"
    success_url = reverse_lazy("skills:resumeline_list")
