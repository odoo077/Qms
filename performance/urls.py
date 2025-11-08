# performance/urls.py
from django.urls import path
from . import views as v

app_name = "performance"

urlpatterns = [
    # Evaluation Parameters
    path("parameters/", v.EvaluationParameterListView.as_view(), name="parameter_list"),
    path("parameters/new/", v.EvaluationParameterCreateView.as_view(), name="parameter_create"),
    path("parameters/<int:pk>/", v.EvaluationParameterDetailView.as_view(), name="parameter_detail"),
    path("parameters/<int:pk>/edit/", v.EvaluationParameterUpdateView.as_view(), name="parameter_edit"),

    # Evaluation Templates
    path("templates/", v.EvaluationTemplateListView.as_view(), name="template_list"),
    path("templates/new/", v.EvaluationTemplateCreateView.as_view(), name="template_create"),
    path("templates/<int:pk>/", v.EvaluationTemplateDetailView.as_view(), name="template_detail"),
    path("templates/<int:pk>/edit/", v.EvaluationTemplateUpdateView.as_view(), name="template_edit"),

    # Evaluations
    path("evaluations/", v.EvaluationListView.as_view(), name="evaluation_list"),
    path("evaluations/new/", v.EvaluationCreateView.as_view(), name="evaluation_create"),
    path("evaluations/<int:pk>/", v.EvaluationDetailView.as_view(), name="evaluation_detail"),
    path("evaluations/<int:pk>/edit/", v.EvaluationUpdateView.as_view(), name="evaluation_edit"),

    # Objectives
    path("objectives/", v.ObjectiveListView.as_view(), name="objective_list"),
    path("objectives/new/", v.ObjectiveCreateView.as_view(), name="objective_create"),
    path("objectives/<int:pk>/", v.ObjectiveDetailView.as_view(), name="objective_detail"),
    path("objectives/<int:pk>/edit/", v.ObjectiveUpdateView.as_view(), name="objective_edit"),

    # KPIs
    path("kpis/", v.KPIListView.as_view(), name="kpi_list"),
    path("kpis/new/", v.KPICreateView.as_view(), name="kpi_create"),
    path("kpis/<int:pk>/", v.KPIDetailView.as_view(), name="kpi_detail"),
    path("kpis/<int:pk>/edit/", v.KPIUpdateView.as_view(), name="kpi_edit"),

    # Tasks
    path("tasks/", v.TaskListView.as_view(), name="task_list"),
    path("tasks/new/", v.TaskCreateView.as_view(), name="task_create"),
    path("tasks/<int:pk>/", v.TaskDetailView.as_view(), name="task_detail"),
    path("tasks/<int:pk>/edit/", v.TaskUpdateView.as_view(), name="task_edit"),
]
