# performance/views.py
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DetailView
from base.views import BaseScopedListView, apply_search_filters
from . import models as m
from . import forms as f


# ===============================================================
# Evaluation Parameters
# ===============================================================
class EvaluationParameterListView(LoginRequiredMixin, BaseScopedListView):
    model = m.EvaluationParameter
    template_name = "performance/evaluationparameter_list.html"
    paginate_by = 24

    def get_queryset(self):
        qs = m.EvaluationParameter.objects.with_acl("view").order_by("name")
        qs = apply_search_filters(self.request, qs, search_fields=["name", "description"])
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_add_parameter"] = self.request.user.has_perm("performance.add_evaluationparameter")
        ctx["parameter_change_ids"] = set(
            m.EvaluationParameter.objects.with_acl("change").values_list("id", flat=True)
        )
        return ctx


class EvaluationParameterCreateView(LoginRequiredMixin, CreateView):
    model = m.EvaluationParameter
    form_class = f.EvaluationParameterForm
    template_name = "performance/evaluationparameter_form.html"
    success_url = reverse_lazy("performance:parameter_list")


class EvaluationParameterUpdateView(LoginRequiredMixin, UpdateView):
    model = m.EvaluationParameter
    form_class = f.EvaluationParameterForm
    template_name = "performance/evaluationparameter_form.html"
    success_url = reverse_lazy("performance:parameter_list")


class EvaluationParameterDetailView(LoginRequiredMixin, DetailView):
    model = m.EvaluationParameter
    template_name = "performance/evaluationparameter_detail.html"


# ===============================================================
# Evaluation Templates
# ===============================================================
class EvaluationTemplateListView(LoginRequiredMixin, BaseScopedListView):
    model = m.EvaluationTemplate
    template_name = "performance/evaluationtemplate_list.html"
    paginate_by = 24

    def get_queryset(self):
        qs = m.EvaluationTemplate.objects.with_acl("view").select_related("company").order_by("name")
        qs = apply_search_filters(self.request, qs, search_fields=["name", "description"])
        return qs


class EvaluationTemplateCreateView(LoginRequiredMixin, CreateView):
    model = m.EvaluationTemplate
    form_class = f.EvaluationTemplateForm
    template_name = "performance/evaluationtemplate_form.html"
    success_url = reverse_lazy("performance:template_list")


class EvaluationTemplateUpdateView(LoginRequiredMixin, UpdateView):
    model = m.EvaluationTemplate
    form_class = f.EvaluationTemplateForm
    template_name = "performance/evaluationtemplate_form.html"
    success_url = reverse_lazy("performance:template_list")


class EvaluationTemplateDetailView(LoginRequiredMixin, DetailView):
    model = m.EvaluationTemplate
    template_name = "performance/evaluationtemplate_detail.html"


# ===============================================================
# Evaluations
# ===============================================================
class EvaluationListView(LoginRequiredMixin, BaseScopedListView):
    model = m.Evaluation
    template_name = "performance/evaluation_list.html"
    paginate_by = 24

    def get_queryset(self):
        qs = (
            m.Evaluation.objects.with_acl("view")
            .select_related("company", "employee", "template")
            .order_by("-created_at")
        )
        qs = apply_search_filters(
            self.request,
            qs,
            search_fields=["employee__name", "template__name", "state"],
        )
        return qs


class EvaluationCreateView(LoginRequiredMixin, CreateView):
    model = m.Evaluation
    form_class = f.EvaluationForm
    template_name = "performance/evaluation_form.html"
    success_url = reverse_lazy("performance:evaluation_list")


class EvaluationUpdateView(LoginRequiredMixin, UpdateView):
    model = m.Evaluation
    form_class = f.EvaluationForm
    template_name = "performance/evaluation_form.html"
    success_url = reverse_lazy("performance:evaluation_list")


class EvaluationDetailView(LoginRequiredMixin, DetailView):
    model = m.Evaluation
    template_name = "performance/evaluation_detail.html"


# ===============================================================
# Objectives
# ===============================================================
class ObjectiveListView(LoginRequiredMixin, BaseScopedListView):
    model = m.Objective
    template_name = "performance/objective_list.html"
    paginate_by = 24

    def get_queryset(self):
        qs = m.Objective.objects.with_acl("view").select_related("employee", "department")
        qs = apply_search_filters(
            self.request,
            qs,
            search_fields=["name", "description", "employee__name", "department__name"],
        )
        return qs


class ObjectiveCreateView(LoginRequiredMixin, CreateView):
    model = m.Objective
    form_class = f.ObjectiveForm
    template_name = "performance/objective_form.html"
    success_url = reverse_lazy("performance:objective_list")


class ObjectiveUpdateView(LoginRequiredMixin, UpdateView):
    model = m.Objective
    form_class = f.ObjectiveForm
    template_name = "performance/objective_form.html"
    success_url = reverse_lazy("performance:objective_list")


class ObjectiveDetailView(LoginRequiredMixin, DetailView):
    model = m.Objective
    template_name = "performance/objective_detail.html"


# ===============================================================
# KPIs
# ===============================================================
class KPIListView(LoginRequiredMixin, BaseScopedListView):
    model = m.KPI
    template_name = "performance/kpi_list.html"
    paginate_by = 24

    def get_queryset(self):
        qs = m.KPI.objects.with_acl("view").order_by("name")
        qs = apply_search_filters(self.request, qs, search_fields=["name", "description"])
        return qs


class KPICreateView(LoginRequiredMixin, CreateView):
    model = m.KPI
    form_class = f.KPIForm
    template_name = "performance/kpi_form.html"
    success_url = reverse_lazy("performance:kpi_list")


class KPIUpdateView(LoginRequiredMixin, UpdateView):
    model = m.KPI
    form_class = f.KPIForm
    template_name = "performance/kpi_form.html"
    success_url = reverse_lazy("performance:kpi_list")


class KPIDetailView(LoginRequiredMixin, DetailView):
    model = m.KPI
    template_name = "performance/kpi_detail.html"


# ===============================================================
# Tasks
# ===============================================================
class TaskListView(LoginRequiredMixin, BaseScopedListView):
    model = m.Task
    template_name = "performance/task_list.html"
    paginate_by = 24

    def get_queryset(self):
        qs = m.Task.objects.with_acl("view").select_related("assignee").order_by("-due_date")
        qs = apply_search_filters(self.request, qs, search_fields=["name", "assignee__name", "status"])
        return qs


class TaskCreateView(LoginRequiredMixin, CreateView):
    model = m.Task
    form_class = f.TaskForm
    template_name = "performance/task_form.html"
    success_url = reverse_lazy("performance:task_list")


class TaskUpdateView(LoginRequiredMixin, UpdateView):
    model = m.Task
    form_class = f.TaskForm
    template_name = "performance/task_form.html"
    success_url = reverse_lazy("performance:task_list")


class TaskDetailView(LoginRequiredMixin, DetailView):
    model = m.Task
    template_name = "performance/task_detail.html"
