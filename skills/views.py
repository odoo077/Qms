# skills/views.py
# ============================================================
# Skills Views – FINAL (ACL + Company Scope compliant)
# Compatible 100% with base + hr architecture
# ============================================================

from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.urls import reverse_lazy

from base.views import (
    BaseScopedListView,
    BaseScopedUpdateView,
    BaseScopedDeleteView,
    BaseScopedCreateView,
    ConfirmDeleteMixin,
    apply_search_filters,
)

from .models import (
    SkillType,
    SkillLevel,
    Skill,
    EmployeeSkill,
    ResumeLine,
    ResumeLineType,
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
# SKILL TYPE
# ============================================================

class SkillTypeListView(LoginRequiredMixin, BaseScopedListView):
    model = SkillType
    template_name = "skills/skilltype_list.html"
    paginate_by = 24

    def get_queryset(self):
        qs = SkillType.objects.order_by("sequence", "name")
        return apply_search_filters(self.request, qs, search_fields=["name"])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_add_skilltype"] = self.request.user.has_perm("skills.add_skilltype")
        ctx["can_delete_skilltype"] = self.request.user.has_perm("skills.delete_skilltype")
        return ctx


class SkillTypeCreateView(LoginRequiredMixin, PermissionRequiredMixin, BaseScopedCreateView):
    model = SkillType
    form_class = SkillTypeForm
    template_name = "skills/skilltype_form.html"
    success_url = reverse_lazy("skills:skilltype_list")
    permission_required = "skills.add_skilltype"


class SkillTypeUpdateView(LoginRequiredMixin, PermissionRequiredMixin, BaseScopedUpdateView):
    model = SkillType
    form_class = SkillTypeForm
    template_name = "skills/skilltype_form.html"
    success_url = reverse_lazy("skills:skilltype_list")
    permission_required = ["skills.change_skilltype", "skills.delete_skilltype"]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_delete_object"] = self.request.user.has_perm("skills.delete_skilltype")
        return ctx


class SkillTypeDeleteView(
    LoginRequiredMixin,
    PermissionRequiredMixin,
    ConfirmDeleteMixin,
    BaseScopedDeleteView,
):
    model = SkillType
    permission_required = "skills.delete_skilltype"
    back_url_name = "skills:skilltype_list"
    object_label_field = "name"


# ============================================================
# SKILL LEVEL
# ============================================================

class SkillLevelListView(LoginRequiredMixin, BaseScopedListView):
    model = SkillLevel
    template_name = "skills/skilllevel_list.html"
    paginate_by = 24

    def get_queryset(self):
        qs = SkillLevel.objects.select_related("skill_type").order_by(
            "skill_type__sequence", "level_progress"
        )
        return apply_search_filters(
            self.request, qs, search_fields=["name", "skill_type__name"]
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_add_skilllevel"] = self.request.user.has_perm("skills.add_skilllevel")
        ctx["can_delete_skilllevel"] = self.request.user.has_perm("skills.delete_skilllevel")
        return ctx


class SkillLevelCreateView(LoginRequiredMixin, PermissionRequiredMixin, BaseScopedCreateView):
    model = SkillLevel
    form_class = SkillLevelForm
    template_name = "skills/skilllevel_form.html"
    success_url = reverse_lazy("skills:skilllevel_list")
    permission_required = "skills.add_skilllevel"


class SkillLevelUpdateView(LoginRequiredMixin, PermissionRequiredMixin, BaseScopedUpdateView):
    model = SkillLevel
    form_class = SkillLevelForm
    template_name = "skills/skilllevel_form.html"
    success_url = reverse_lazy("skills:skilllevel_list")
    permission_required = ["skills.change_skilllevel", "skills.delete_skilllevel"]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_delete_object"] = self.request.user.has_perm("skills.delete_skilllevel")
        return ctx


class SkillLevelDeleteView(
    LoginRequiredMixin,
    PermissionRequiredMixin,
    ConfirmDeleteMixin,
    BaseScopedDeleteView,
):
    model = SkillLevel
    permission_required = "skills.delete_skilllevel"
    back_url_name = "skills:skilllevel_list"
    object_label_field = "name"


# ============================================================
# SKILL
# ============================================================

class SkillListView(LoginRequiredMixin, BaseScopedListView):
    model = Skill
    template_name = "skills/skill_list.html"
    paginate_by = 24

    def get_queryset(self):
        qs = Skill.objects.select_related("skill_type").order_by(
            "skill_type__sequence", "name"
        )
        return apply_search_filters(
            self.request, qs, search_fields=["name", "skill_type__name"]
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_add_skill"] = self.request.user.has_perm("skills.add_skill")
        ctx["can_delete_skill"] = self.request.user.has_perm("skills.delete_skill")
        return ctx


class SkillCreateView(LoginRequiredMixin, PermissionRequiredMixin, BaseScopedCreateView):
    model = Skill
    form_class = SkillForm
    template_name = "skills/skill_form.html"
    success_url = reverse_lazy("skills:skill_list")
    permission_required = "skills.add_skill"


class SkillUpdateView(LoginRequiredMixin, PermissionRequiredMixin, BaseScopedUpdateView):
    model = Skill
    form_class = SkillForm
    template_name = "skills/skill_form.html"
    success_url = reverse_lazy("skills:skill_list")
    permission_required = ["skills.change_skill", "skills.delete_skill"]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_delete_object"] = self.request.user.has_perm("skills.delete_skill")
        return ctx


class SkillDeleteView(
    LoginRequiredMixin,
    PermissionRequiredMixin,
    ConfirmDeleteMixin,
    BaseScopedDeleteView,
):
    model = Skill
    permission_required = "skills.delete_skill"
    back_url_name = "skills:skill_list"
    object_label_field = "name"


# ============================================================
# EMPLOYEE SKILL (ACL PROTECTED)
# ============================================================

class EmployeeSkillListView(LoginRequiredMixin, BaseScopedListView):
    model = EmployeeSkill
    template_name = "skills/employeeskill_list.html"
    paginate_by = 24

    def get_queryset(self):
        qs = EmployeeSkill.acl.filter(
            company_id=self.request.company_id
        ).select_related(
            "employee", "skill_type", "skill", "skill_level"
        ).order_by("employee__name")
        return apply_search_filters(
            self.request,
            qs,
            search_fields=["employee__name", "skill__name", "skill_type__name"],
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_add_employeeskill"] = self.request.user.has_perm(
            "skills.add_employeeskill"
        )
        return ctx


class EmployeeSkillCreateView(LoginRequiredMixin, PermissionRequiredMixin, BaseScopedCreateView):
    model = EmployeeSkill
    form_class = EmployeeSkillForm
    template_name = "skills/employeeskill_form.html"
    success_url = reverse_lazy("skills:employeeskill_list")
    permission_required = "skills.add_employeeskill"


class EmployeeSkillUpdateView(LoginRequiredMixin, PermissionRequiredMixin, BaseScopedUpdateView):
    model = EmployeeSkill
    form_class = EmployeeSkillForm
    template_name = "skills/employeeskill_form.html"
    success_url = reverse_lazy("skills:employeeskill_list")
    permission_required = "skills.change_employeeskill"

    def get_object(self, queryset=None):
        return EmployeeSkill.acl.get(pk=self.kwargs["pk"])


class EmployeeSkillDeleteView(
    LoginRequiredMixin,
    PermissionRequiredMixin,
    ConfirmDeleteMixin,
    BaseScopedDeleteView,
):
    model = EmployeeSkill
    permission_required = "skills.delete_employeeskill"
    back_url_name = "skills:employeeskill_list"
    object_label_field = "skill"

    def get_object(self, queryset=None):
        return EmployeeSkill.acl.get(pk=self.kwargs["pk"])


# ============================================================
# RESUME LINE TYPE
# ============================================================

class ResumeLineTypeListView(LoginRequiredMixin, BaseScopedListView):
    model = ResumeLineType
    template_name = "skills/resumelinetype_list.html"
    paginate_by = 24

    def get_queryset(self):
        qs = ResumeLineType.objects.order_by("sequence", "name")
        return apply_search_filters(self.request, qs, search_fields=["name"])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_add_resumelinetype"] = self.request.user.has_perm(
            "skills.add_resumelinetype"
        )
        ctx["can_delete_resumelinetype"] = self.request.user.has_perm(
            "skills.delete_resumelinetype"
        )
        return ctx


class ResumeLineTypeCreateView(LoginRequiredMixin, PermissionRequiredMixin, BaseScopedCreateView):
    model = ResumeLineType
    form_class = ResumeLineTypeForm
    template_name = "skills/resumelinetype_form.html"
    success_url = reverse_lazy("skills:resumelinetype_list")
    permission_required = "skills.add_resumelinetype"


class ResumeLineTypeUpdateView(LoginRequiredMixin, PermissionRequiredMixin, BaseScopedUpdateView):
    model = ResumeLineType
    form_class = ResumeLineTypeForm
    template_name = "skills/resumelinetype_form.html"
    success_url = reverse_lazy("skills:resumelinetype_list")
    permission_required = ["skills.change_resumelinetype", "skills.delete_resumelinetype"]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_delete_object"] = self.request.user.has_perm(
            "skills.delete_resumelinetype"
        )
        return ctx


class ResumeLineTypeDeleteView(
    LoginRequiredMixin,
    PermissionRequiredMixin,
    ConfirmDeleteMixin,
    BaseScopedDeleteView,
):
    model = ResumeLineType
    permission_required = "skills.delete_resumelinetype"
    back_url_name = "skills:resumelinetype_list"
    object_label_field = "name"


# ============================================================
# RESUME LINE (ACL PROTECTED)
# ============================================================

class ResumeLineListView(LoginRequiredMixin, BaseScopedListView):
    model = ResumeLine
    template_name = "skills/resumeline_list.html"
    paginate_by = 24

    def get_queryset(self):
        qs = ResumeLine.acl.filter(
            company_id=self.request.company_id
        ).select_related("employee", "line_type").order_by("employee__name")
        return apply_search_filters(
            self.request,
            qs,
            search_fields=["name", "employee__name", "line_type__name"],
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_add_resumeline"] = self.request.user.has_perm("skills.add_resumeline")
        return ctx


class ResumeLineCreateView(LoginRequiredMixin, PermissionRequiredMixin, BaseScopedCreateView):
    model = ResumeLine
    form_class = ResumeLineForm
    template_name = "skills/resumeline_form.html"
    success_url = reverse_lazy("skills:resumeline_list")
    permission_required = "skills.add_resumeline"


class ResumeLineUpdateView(LoginRequiredMixin, PermissionRequiredMixin, BaseScopedUpdateView):
    model = ResumeLine
    form_class = ResumeLineForm
    template_name = "skills/resumeline_form.html"
    success_url = reverse_lazy("skills:resumeline_list")
    permission_required = "skills.change_resumeline"

    def get_object(self, queryset=None):
        return ResumeLine.acl.get(pk=self.kwargs["pk"])


class ResumeLineDeleteView(
    LoginRequiredMixin,
    PermissionRequiredMixin,
    ConfirmDeleteMixin,
    BaseScopedDeleteView,
):
    model = ResumeLine
    permission_required = "skills.delete_resumeline"
    back_url_name = "skills:resumeline_list"
    object_label_field = "name"

    def get_object(self, queryset=None):
        return ResumeLine.acl.get(pk=self.kwargs["pk"])
