# skills/views.py
# ============================================================
# Skills Views – Odoo-like (PRO MODE)
# - بحث + فلاتر + ترتيب + pagination
# - حفظ آخر فلاتر المستخدم في session (لكل صفحة قائمة)
# - تجهيز سياق غني لبناء UI احترافي لاحقًا
# ============================================================

from __future__ import annotations

from typing import Dict, Iterable, Tuple

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from .forms import (
    EmployeeSkillForm,
    ResumeLineForm,
    ResumeLineTypeForm,
    SkillForm,
    SkillLevelForm,
    SkillTypeForm,
)
from .models import (
    EmployeeSkill,
    ResumeLine,
    ResumeLineType,
    Skill,
    SkillLevel,
    SkillType,
)
from .services import (
    EmployeeSkillInput,
    add_employee_skill,
    delete_employee_skill,
    update_employee_skill,
)


# ============================================================
# Shared helpers / mixins
# ============================================================

CONFIRM_DELETE_TEMPLATE = "partials/confirm_delete.html"


class SavedFiltersListMixin:
    """
    مزيج احترافي للقوائم:
    - يدعم حفظ الفلاتر في session
    - يدعم البحث q
    - يدعم ترتيب order عبر GET
    - يدعم reset حقيقي (يمسح session + GET)
    - يحقن params المعتمدة في context لبناء UI لاحقًا (chips…)
    """

    session_key: str = ""  # يجب ضبطه في كل View
    search_param: str = "q"
    order_param: str = "o"
    reset_param: str = "reset"

    # مسموح به للترتيب (منع أي order_by عشوائي)
    allowed_ordering: Dict[str, Tuple[str, ...]] = {}

    def _get_params(self) -> Dict[str, str]:
        request = self.request

        # --------------------------------------------------
        # RESET: مسح session + تجاهل أي GET
        # --------------------------------------------------
        if request.GET.get(self.reset_param) == "1":
            if self.session_key and self.session_key in request.session:
                del request.session[self.session_key]
            return {}

        # --------------------------------------------------
        # GET له أولوية على session
        # --------------------------------------------------
        if request.GET:
            params = request.GET.copy()
        else:
            params = request.session.get(self.session_key, {}).copy()

        # --------------------------------------------------
        # حفظ الفلاتر في session (استثناء page و reset)
        # --------------------------------------------------
        if self.session_key:
            request.session[self.session_key] = {
                k: v for k, v in params.items()
                if v and k not in ("page", self.reset_param)
            }

        return params

    def _apply_search(self, qs, params: Dict[str, str], fields: Iterable[str]):
        q = (params.get(self.search_param) or "").strip()
        if not q:
            return qs

        query = Q()
        for f in fields:
            query |= Q(**{f"{f}__icontains": q})
        return qs.filter(query)

    def _apply_ordering(self, qs, params: Dict[str, str], default: Tuple[str, ...]):
        """
        order key is params[o] where o is a key in allowed_ordering
        """
        key = (params.get(self.order_param) or "").strip()
        if key and key in self.allowed_ordering:
            return qs.order_by(*self.allowed_ordering[key])
        return qs.order_by(*default)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        params = getattr(self, "_params", None) or self._get_params()

        ctx.update({
            "params": params,
            "current_params": params,
            "q": (params.get(self.search_param) or "").strip(),
            "ordering_key": (params.get(self.order_param) or "").strip(),
            "active_filters": self.build_active_filters(params),
        })
        return ctx

    def build_active_filters(self, params: Dict[str, str]) -> list[dict]:
        """
        يبني قائمة فلاتر نشطة بشكل عام (قابلة للعرض كـ chips في UI).
        يمكن override في أي View عند الحاجة.
        """
        filters = []

        q = (params.get(self.search_param) or "").strip()
        if q:
            filters.append({
                "key": self.search_param,
                "label": "Search",
                "value": q,
            })

        for key, value in params.items():
            if key in (self.search_param, self.order_param, "page", self.reset_param):
                continue
            if value:
                filters.append({
                    "key": key,
                    "label": key.replace("_", " ").title(),
                    "value": value,
                })

        return filters

class CRUDMessagesMixin:
    """
    رسائل نجاح/فشل قياسية لكل Create/Update/Delete
    """
    success_message_create = "Created successfully."
    success_message_update = "Updated successfully."
    success_message_delete = "Deleted successfully."

    def form_valid(self, form):
        response = super().form_valid(form)
        if isinstance(self, CreateView):
            messages.success(self.request, self.success_message_create)
        else:
            messages.success(self.request, self.success_message_update)
        return response

    def form_invalid(self, form):
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)

    def delete(self, request, *args, **kwargs):
        messages.success(request, self.success_message_delete)
        return super().delete(request, *args, **kwargs)


# ============================================================
# Skill Type
# ============================================================

class SkillTypeListView(LoginRequiredMixin, SavedFiltersListMixin, ListView):
    model = SkillType
    template_name = "skills/skilltype_list.html"
    paginate_by = 25
    session_key = "skills_skilltype_list_filters"

    allowed_ordering = {
        "name": ("name",),
        "seq": ("sequence", "name"),
        "-seq": ("-sequence", "name"),
        "-name": ("-name",),
    }

    def get_queryset(self):
        qs = SkillType.objects.all()

        self._params = self._get_params()
        params = self._params

        # Filters
        active = (params.get("active") or "").strip()
        if active == "1":
            qs = qs.filter(active=True)
        elif active == "0":
            qs = qs.filter(active=False)

        is_cert = (params.get("is_certification") or "").strip()
        if is_cert == "1":
            qs = qs.filter(is_certification=True)
        elif is_cert == "0":
            qs = qs.filter(is_certification=False)

        # Search
        qs = self._apply_search(qs, params, fields=["name"])

        # Ordering
        return self._apply_ordering(qs, params, default=("sequence", "name"))


class SkillTypeCreateView(LoginRequiredMixin, CRUDMessagesMixin, CreateView):
    model = SkillType
    form_class = SkillTypeForm
    template_name = "skills/skilltype_form.html"
    success_url = reverse_lazy("skills:skilltype_list")
    success_message_create = "Skill type created successfully."


class SkillTypeUpdateView(LoginRequiredMixin, CRUDMessagesMixin, UpdateView):
    model = SkillType
    form_class = SkillTypeForm
    template_name = "skills/skilltype_form.html"
    success_url = reverse_lazy("skills:skilltype_list")
    success_message_update = "Skill type updated successfully."


class SkillTypeDeleteView(LoginRequiredMixin, CRUDMessagesMixin, DeleteView):
    model = SkillType
    template_name = CONFIRM_DELETE_TEMPLATE
    success_url = reverse_lazy("skills:skilltype_list")
    success_message_delete = "Skill type deleted successfully."


# ============================================================
# Skill Level
# ============================================================

class SkillLevelListView(LoginRequiredMixin, SavedFiltersListMixin, ListView):
    model = SkillLevel
    template_name = "skills/skilllevel_list.html"
    paginate_by = 25
    session_key = "skills_skilllevel_list_filters"

    allowed_ordering = {
        "type": ("skill_type__sequence", "skill_type__name", "level_progress", "name"),
        "progress": ("level_progress", "name"),
        "-progress": ("-level_progress", "name"),
        "name": ("name",),
        "-name": ("-name",),
    }

    def get_queryset(self):
        qs = SkillLevel.objects.select_related("skill_type")

        self._params = self._get_params()
        params = self._params

        # Filters
        skill_type_id = (params.get("skill_type") or "").strip()
        if skill_type_id:
            qs = qs.filter(skill_type_id=skill_type_id)

        active = (params.get("active") or "").strip()
        if active == "1":
            qs = qs.filter(active=True)
        elif active == "0":
            qs = qs.filter(active=False)

        default_level = (params.get("default_level") or "").strip()
        if default_level == "1":
            qs = qs.filter(default_level=True)
        elif default_level == "0":
            qs = qs.filter(default_level=False)

        # Search
        qs = self._apply_search(qs, params, fields=["name", "skill_type__name"])

        # Ordering
        return self._apply_ordering(
            qs,
            params,
            default=("skill_type__sequence", "level_progress", "name"),
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["skilltypes"] = SkillType.objects.filter(active=True).order_by("sequence", "name")
        return ctx


class SkillLevelCreateView(LoginRequiredMixin, CRUDMessagesMixin, CreateView):
    model = SkillLevel
    form_class = SkillLevelForm
    template_name = "skills/skilllevel_form.html"
    success_url = reverse_lazy("skills:skilllevel_list")
    success_message_create = "Skill level created successfully."


class SkillLevelUpdateView(LoginRequiredMixin, CRUDMessagesMixin, UpdateView):
    model = SkillLevel
    form_class = SkillLevelForm
    template_name = "skills/skilllevel_form.html"
    success_url = reverse_lazy("skills:skilllevel_list")
    success_message_update = "Skill level updated successfully."


class SkillLevelDeleteView(LoginRequiredMixin, CRUDMessagesMixin, DeleteView):
    model = SkillLevel
    template_name = CONFIRM_DELETE_TEMPLATE
    success_url = reverse_lazy("skills:skilllevel_list")
    success_message_delete = "Skill level deleted successfully."


# ============================================================
# Skill
# ============================================================

class SkillListView(LoginRequiredMixin, SavedFiltersListMixin, ListView):
    model = Skill
    template_name = "skills/skill_list.html"
    paginate_by = 25
    context_object_name = "skills"

    # Session key for saved filters
    session_key = "skills_skill_list_filters"

    # Allowed ordering (Odoo-like)
    allowed_ordering = {
        "type": ("skill_type__sequence", "skill_type__name", "sequence", "name"),
        "seq": ("sequence", "name"),
        "-seq": ("-sequence", "name"),
        "name": ("name",),
        "-name": ("-name",),
    }

    # --------------------------------------------------
    # Queryset
    # --------------------------------------------------
    def get_queryset(self):
        qs = Skill.objects.select_related("skill_type")

        # --------------------------------------------------
        # Load params (GET or session)
        # --------------------------------------------------
        self._params = self._get_params()
        params = self._params

        # --------------------------------------------------
        # Store params as view attributes (USED EVERYWHERE)
        # --------------------------------------------------
        self.q = (params.get("q") or "").strip()
        self.active = (params.get("active") or "").strip()

        skill_type_id = (params.get("skill_type") or "").strip()
        self.skill_type = None
        if skill_type_id:
            self.skill_type = SkillType.objects.filter(pk=skill_type_id).first()

        # --------------------------------------------------
        # Filters
        # --------------------------------------------------
        if self.skill_type:
            qs = qs.filter(skill_type=self.skill_type)

        if self.active == "1":
            qs = qs.filter(active=True)
        elif self.active == "0":
            qs = qs.filter(active=False)

        # --------------------------------------------------
        # Search
        # --------------------------------------------------
        qs = self._apply_search(
            qs,
            params,
            fields=[
                "name",
                "skill_type__name",
            ],
        )

        # --------------------------------------------------
        # Ordering
        # --------------------------------------------------
        return self._apply_ordering(
            qs,
            params,
            default=("skill_type__sequence", "sequence", "name"),
        )

    # --------------------------------------------------
    # Context
    # --------------------------------------------------
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        # --------------------------------------------------
        # Filter choices (خاص بهذه الصفحة فقط)
        # --------------------------------------------------
        ctx["skilltypes"] = SkillType.objects.filter(active=True).order_by(
            "sequence", "name"
        )

        return ctx


class SkillCreateView(LoginRequiredMixin, CRUDMessagesMixin, CreateView):
    model = Skill
    form_class = SkillForm
    template_name = "skills/skill_form.html"
    success_url = reverse_lazy("skills:skill_list")
    success_message_create = "Skill created successfully."


class SkillUpdateView(LoginRequiredMixin, CRUDMessagesMixin, UpdateView):
    model = Skill
    form_class = SkillForm
    template_name = "skills/skill_form.html"
    success_url = reverse_lazy("skills:skill_list")
    success_message_update = "Skill updated successfully."


class SkillDeleteView(LoginRequiredMixin, CRUDMessagesMixin, DeleteView):
    model = Skill
    template_name = CONFIRM_DELETE_TEMPLATE
    success_url = reverse_lazy("skills:skill_list")
    success_message_delete = "Skill deleted successfully."


# ============================================================
# Employee Skill (Services-driven, Odoo-like)
# ============================================================

class EmployeeSkillListView(LoginRequiredMixin, SavedFiltersListMixin, ListView):
    model = EmployeeSkill
    template_name = "skills/employeeskill_list.html"
    paginate_by = 25
    session_key = "skills_employeeskill_list_filters"

    allowed_ordering = {
        "employee": ("employee__name", "skill_type__sequence", "skill__name"),
        "-employee": ("-employee__name", "skill_type__sequence", "skill__name"),
        "skill": ("skill__name",),
        "-skill": ("-skill__name",),
        "type": ("skill_type__sequence", "skill__name"),
    }

    def get_queryset(self):
        qs = EmployeeSkill.objects.select_related(
            "employee",
            "employee__company",
            "skill_type",
            "skill",
            "skill_level",
        )

        self._params = self._get_params()
        params = self._params

        # Filters
        employee_id = (params.get("employee") or "").strip()
        if employee_id:
            qs = qs.filter(employee_id=employee_id)

        skill_type_id = (params.get("skill_type") or "").strip()
        if skill_type_id:
            qs = qs.filter(skill_type_id=skill_type_id)

        skill_id = (params.get("skill") or "").strip()
        if skill_id:
            qs = qs.filter(skill_id=skill_id)

        level_id = (params.get("skill_level") or "").strip()
        if level_id:
            qs = qs.filter(skill_level_id=level_id)

        active = (params.get("active") or "").strip()
        if active == "1":
            qs = qs.filter(active=True)
        elif active == "0":
            qs = qs.filter(active=False)

        # Search
        qs = self._apply_search(
            qs,
            params,
            fields=[
                "employee__name",
                "skill__name",
                "skill_type__name",
                "skill_level__name",
                "employee__company__name",
            ],
        )

        # Ordering
        return self._apply_ordering(qs, params, default=("employee__name", "skill_type__sequence", "skill__name"))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        # هذه القوائم تُفيد UI لاحقًا (dropdowns/filters)
        # ملاحظة: لم أستورد Employee هنا لتجنب اعتماديات إضافية؛
        # إن أردت فلتر employee كقائمة، أخبرني وأربطه بشكل محسوب (مع select_related).
        ctx["skilltypes"] = SkillType.objects.filter(active=True).order_by("sequence", "name")
        ctx["skills"] = Skill.objects.filter(active=True).select_related("skill_type").order_by("skill_type__sequence", "name")
        ctx["levels"] = SkillLevel.objects.filter(active=True).select_related("skill_type").order_by("skill_type__sequence", "level_progress")
        return ctx


class EmployeeSkillCreateView(LoginRequiredMixin, View):
    """
    Create via services.add_employee_skill (Odoo-like strict create)
    """
    template_name = "skills/employeeskill_form.html"

    def get(self, request):
        form = EmployeeSkillForm()
        return render(request, self.template_name, {"form": form})

    def post(self, request):
        form = EmployeeSkillForm(request.POST)

        if not form.is_valid():
            messages.error(request, "Please correct the errors below.")
            return render(request, self.template_name, {"form": form})

        cd = form.cleaned_data

        try:
            add_employee_skill(
                EmployeeSkillInput(
                    employee_id=cd["employee"].id,
                    skill_type_id=cd["skill_type"].id,
                    skill_id=cd["skill"].id,
                    skill_level_id=cd["skill_level"].id,
                    valid_from=cd.get("valid_from"),
                    valid_to=cd.get("valid_to"),
                    note=cd.get("note", ""),
                    created_by_id=request.user.id,
                    updated_by_id=request.user.id,
                )
            )
        except ValidationError as exc:
            form.add_error(None, exc)
            messages.error(request, "Validation error.")
            return render(request, self.template_name, {"form": form})
        except Exception as exc:
            form.add_error(None, str(exc))
            messages.error(request, "An unexpected error occurred.")
            return render(request, self.template_name, {"form": form})

        messages.success(request, "Employee skill added successfully.")
        return HttpResponseRedirect(reverse("skills:employeeskill_list"))


class EmployeeSkillUpdateView(LoginRequiredMixin, View):
    """
    Update via services.update_employee_skill
    """
    template_name = "skills/employeeskill_form.html"

    def get(self, request, pk: int):
        obj = get_object_or_404(EmployeeSkill, pk=pk)
        form = EmployeeSkillForm(instance=obj)
        return render(request, self.template_name, {"form": form, "object": obj})

    def post(self, request, pk: int):
        obj = get_object_or_404(EmployeeSkill, pk=pk)
        form = EmployeeSkillForm(request.POST, instance=obj)

        if not form.is_valid():
            messages.error(request, "Please correct the errors below.")
            return render(request, self.template_name, {"form": form, "object": obj})

        cd = form.cleaned_data

        try:
            update_employee_skill(
                employeeskill_id=obj.id,
                skill_type_id=cd["skill_type"].id,
                skill_id=cd["skill"].id,
                skill_level_id=cd["skill_level"].id,
                valid_from=cd.get("valid_from"),
                valid_to=cd.get("valid_to"),
                note=cd.get("note", ""),
                updated_by_id=request.user.id,
            )
        except ValidationError as exc:
            form.add_error(None, exc)
            messages.error(request, "Validation error.")
            return render(request, self.template_name, {"form": form, "object": obj})
        except Exception as exc:
            form.add_error(None, str(exc))
            messages.error(request, "An unexpected error occurred.")
            return render(request, self.template_name, {"form": form, "object": obj})

        messages.success(request, "Employee skill updated successfully.")
        return HttpResponseRedirect(reverse("skills:employeeskill_list"))


class EmployeeSkillDeleteView(LoginRequiredMixin, View):
    """
    Delete via services.delete_employee_skill
    """
    template_name = CONFIRM_DELETE_TEMPLATE

    def get(self, request, pk: int):
        obj = get_object_or_404(EmployeeSkill, pk=pk)
        return render(request, self.template_name, {"object": obj})

    def post(self, request, pk: int):
        obj = get_object_or_404(EmployeeSkill, pk=pk)
        try:
            delete_employee_skill(obj.id)
        except Exception as exc:
            messages.error(request, str(exc))
            return render(request, self.template_name, {"object": obj})

        messages.success(request, "Employee skill deleted successfully.")
        return HttpResponseRedirect(reverse("skills:employeeskill_list"))


# ============================================================
# Resume Line Type
# ============================================================

class ResumeLineTypeListView(LoginRequiredMixin, SavedFiltersListMixin, ListView):
    model = ResumeLineType
    template_name = "skills/resumelinetype_list.html"
    paginate_by = 25
    session_key = "skills_resumelinetype_list_filters"

    allowed_ordering = {
        "name": ("name",),
        "-name": ("-name",),
        "seq": ("sequence", "name"),
        "-seq": ("-sequence", "name"),
    }

    def get_queryset(self):
        qs = ResumeLineType.objects.all()

        self._params = self._get_params()
        params = self._params

        active = (params.get("active") or "").strip()
        if active == "1":
            qs = qs.filter(active=True)
        elif active == "0":
            qs = qs.filter(active=False)

        qs = self._apply_search(qs, params, fields=["name"])
        return self._apply_ordering(qs, params, default=("sequence", "name"))


class ResumeLineTypeCreateView(LoginRequiredMixin, CRUDMessagesMixin, CreateView):
    model = ResumeLineType
    form_class = ResumeLineTypeForm
    template_name = "skills/resumelinetype_form.html"
    success_url = reverse_lazy("skills:resumelinetype_list")
    success_message_create = "Resume line type created successfully."


class ResumeLineTypeUpdateView(LoginRequiredMixin, CRUDMessagesMixin, UpdateView):
    model = ResumeLineType
    form_class = ResumeLineTypeForm
    template_name = "skills/resumelinetype_form.html"
    success_url = reverse_lazy("skills:resumelinetype_list")
    success_message_update = "Resume line type updated successfully."


class ResumeLineTypeDeleteView(LoginRequiredMixin, CRUDMessagesMixin, DeleteView):
    model = ResumeLineType
    template_name = CONFIRM_DELETE_TEMPLATE
    success_url = reverse_lazy("skills:resumelinetype_list")
    success_message_delete = "Resume line type deleted successfully."


# ============================================================
# Resume Line
# ============================================================

class ResumeLineListView(LoginRequiredMixin, SavedFiltersListMixin, ListView):
    model = ResumeLine
    template_name = "skills/resumeline_list.html"
    paginate_by = 25
    session_key = "skills_resumeline_list_filters"

    allowed_ordering = {
        "employee": ("employee__name", "line_type__sequence", "-date_start", "name"),
        "-employee": ("-employee__name", "line_type__sequence", "-date_start", "name"),
        "type": ("line_type__sequence", "-date_start", "name"),
        "date": ("-date_start", "name"),
        "-date": ("date_start", "name"),
        "name": ("name",),
        "-name": ("-name",),
    }

    def get_queryset(self):
        qs = ResumeLine.objects.select_related(
            "employee",
            "employee__company",
            "line_type",
        )

        self._params = self._get_params()
        params = self._params

        # --------------------------------------------------
        # Filters (FKs → numbers only)
        # --------------------------------------------------
        line_type_id = (params.get("line_type") or "").strip()
        if line_type_id.isdigit():
            qs = qs.filter(line_type_id=int(line_type_id))

        employee_id = (params.get("employee") or "").strip()
        if employee_id.isdigit():
            qs = qs.filter(employee_id=int(employee_id))

        active = (params.get("active") or "").strip()
        if active == "1":
            qs = qs.filter(active=True)
        elif active == "0":
            qs = qs.filter(active=False)

        # --------------------------------------------------
        # Search (TEXT ONLY)
        # --------------------------------------------------
        qs = self._apply_search(
            qs,
            params,
            fields=[
                "employee__name",
                "line_type__name",
                "name",
                "description",
                "employee__company__name",
            ],
        )

        # --------------------------------------------------
        # Ordering
        # --------------------------------------------------
        return self._apply_ordering(
            qs,
            params,
            default=(
                "employee__name",
                "line_type__sequence",
                "-date_start",
                "name",
            ),
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["linetypes"] = ResumeLineType.objects.filter(active=True).order_by("sequence", "name")
        return ctx


class ResumeLineCreateView(LoginRequiredMixin, View):
    template_name = "skills/resumeline_form.html"

    def get(self, request):
        form = ResumeLineForm()
        return render(request, self.template_name, {"form": form})

    def post(self, request):
        form = ResumeLineForm(request.POST, request.FILES)

        if not form.is_valid():
            messages.error(request, "Please correct the errors below.")
            return render(request, self.template_name, {"form": form})

        cd = form.cleaned_data

        try:
            from .services import add_resume_line, ResumeLineInput

            add_resume_line(
                ResumeLineInput(
                    employee_id=cd["employee"].id,
                    line_type_id=cd["line_type"].id,
                    name=cd["name"],
                    description=cd.get("description", ""),
                    date_start=cd.get("date_start"),
                    date_end=cd.get("date_end"),
                    external_url=cd.get("external_url", ""),
                    created_by_id=request.user.id,
                    updated_by_id=request.user.id,
                )
            )
        except ValidationError as exc:
            form.add_error(None, exc)
            messages.error(request, "Validation error.")
            return render(request, self.template_name, {"form": form})

        messages.success(request, "Resume line created successfully.")
        return HttpResponseRedirect(reverse("skills:resumeline_list"))



class ResumeLineUpdateView(LoginRequiredMixin, View):
    template_name = "skills/resumeline_form.html"

    def get(self, request, pk: int):
        obj = get_object_or_404(ResumeLine, pk=pk)
        form = ResumeLineForm(instance=obj)
        return render(request, self.template_name, {"form": form, "object": obj})

    def post(self, request, pk: int):
        obj = get_object_or_404(ResumeLine, pk=pk)
        form = ResumeLineForm(request.POST, request.FILES, instance=obj)

        if not form.is_valid():
            messages.error(request, "Please correct the errors below.")
            return render(request, self.template_name, {"form": form, "object": obj})

        cd = form.cleaned_data

        try:
            from .services import update_resume_line

            update_resume_line(
                resumeline_id=obj.id,
                line_type_id=cd["line_type"].id,
                name=cd["name"],
                description=cd.get("description", ""),
                date_start=cd.get("date_start"),
                date_end=cd.get("date_end"),
                external_url=cd.get("external_url", ""),
                updated_by_id=request.user.id,
            )
        except ValidationError as exc:
            form.add_error(None, exc)
            messages.error(request, "Validation error.")
            return render(request, self.template_name, {"form": form, "object": obj})
        except Exception as exc:
            form.add_error(None, str(exc))
            messages.error(request, "An unexpected error occurred.")
            return render(request, self.template_name, {"form": form, "object": obj})

        messages.success(request, "Resume line updated successfully.")
        return HttpResponseRedirect(reverse("skills:resumeline_list"))



class ResumeLineDeleteView(LoginRequiredMixin, CRUDMessagesMixin, DeleteView):
    model = ResumeLine
    template_name = CONFIRM_DELETE_TEMPLATE
    success_url = reverse_lazy("skills:resumeline_list")
    success_message_delete = "Resume line deleted successfully."
