# performance/urls.py
from django.urls import path
from . import views

app_name = "performance"

urlpatterns = [
    # --------------------------------------------------------
    # Evaluation Types (Configuration) - NEW
    # --------------------------------------------------------
    path(
        "types/",
        views.EvaluationTypeListView.as_view(),
        name="evaluation_type_list",
    ),
    path(
        "types/new/",
        views.EvaluationTypeCreateView.as_view(),
        name="evaluation_type_create",
    ),
    path(
        "types/<int:pk>/",
        views.EvaluationTypeDetailView.as_view(),
        name="evaluation_type_detail",
    ),
    path(
        "types/<int:pk>/edit/",
        views.EvaluationTypeUpdateView.as_view(),
        name="evaluation_type_update",
    ),
    path(
        "types/<int:pk>/delete/",
        views.EvaluationTypeDeleteView.as_view(),
        name="evaluation_type_delete",
    ),

    # --------------------------------------------------------
    # Evaluation Approval Steps (per EvaluationType) - NEW
    # --------------------------------------------------------

    path(
        "types/<int:type_pk>/steps/new/",
        views.EvaluationApprovalStepCreateView.as_view(),
        name="evaluation_step_create",
    ),
    path(
        "types/<int:type_pk>/steps/<int:pk>/edit/",
        views.EvaluationApprovalStepUpdateView.as_view(),
        name="evaluation_step_update",
    ),
    path(
        "types/<int:type_pk>/steps/<int:pk>/delete/",
        views.EvaluationApprovalStepDeleteView.as_view(),
        name="evaluation_step_delete",
    ),

    # --------------------------------------------------------
    # Evaluation Parameters
    # --------------------------------------------------------
    path(
        "parameters/",
        views.EvaluationParameterListView.as_view(),
        name="parameter_list",
    ),
    path(
        "parameters/new/",
        views.EvaluationParameterCreateView.as_view(),
        name="parameter_create",
    ),
    path(
        "parameters/<int:pk>/",
        views.EvaluationParameterDetailView.as_view(),
        name="parameter_detail",
    ),
    path(
        "parameters/<int:pk>/edit/",
        views.EvaluationParameterUpdateView.as_view(),
        name="parameter_update",
    ),
    path(
        "parameters/<int:pk>/delete/",
        views.EvaluationParameterDeleteView.as_view(),
        name="parameter_delete",
    ),

    # --------------------------------------------------------
    # Evaluation Templates
    # --------------------------------------------------------
    path(
        "templates/",
        views.EvaluationTemplateListView.as_view(),
        name="template_list",
    ),
    path(
        "templates/new/",
        views.EvaluationTemplateCreateView.as_view(),
        name="template_create",
    ),
    path(
        "templates/<int:pk>/",
        views.EvaluationTemplateDetailView.as_view(),
        name="template_detail",
    ),
    path(
        "templates/<int:pk>/edit/",
        views.EvaluationTemplateUpdateView.as_view(),
        name="template_update",
    ),
    path(
        "templates/<int:pk>/delete/",
        views.EvaluationTemplateDeleteView.as_view(),
        name="template_delete",
    ),

    # --------------------------------------------------------
    # Evaluations
    # --------------------------------------------------------
    path(
        "evaluations/",
        views.EvaluationListView.as_view(),
        name="evaluation_list",
    ),
    path(
        "my-evaluations/",
        views.MyEvaluationListView.as_view(),
        name="my_evaluation_list",
    ),
    path(
        "evaluations/bulk/",
        views.evaluation_bulk_create_view,
        name="evaluation_bulk_create",
    ),
    path(
        "evaluations/new/",
        views.EvaluationCreateView.as_view(),
        name="evaluation_create",
    ),
    path(
        "evaluations/<int:pk>/",
        views.EvaluationDetailView.as_view(),
        name="evaluation_detail",
    ),
    path(
        "evaluations/<int:pk>/edit/",
        views.EvaluationUpdateView.as_view(),
        name="evaluation_update",
    ),
    path(
        "evaluations/<int:pk>/delete/",
        views.EvaluationDeleteView.as_view(),
        name="evaluation_delete",
    ),

    # Evaluation Workflow Actions (Submit / Approve / Reject)
    path(
        "evaluations/<int:pk>/submit/",
        views.evaluation_submit_view,
        name="evaluation_submit",
    ),
    path(
        "evaluations/<int:pk>/approve-step/",
        views.evaluation_approve_step_view,
        name="evaluation_approve_step",
    ),
    path(
        "evaluations/<int:pk>/reject-step/",
        views.evaluation_reject_step_view,
        name="evaluation_reject_step",
    ),

    # --------------------------------------------------------
    # Objectives
    # --------------------------------------------------------
    path(
        "objectives/",
        views.ObjectiveListView.as_view(),
        name="objective_list",
    ),
    path(
        "objectives/new/",
        views.ObjectiveCreateView.as_view(),
        name="objective_create",
    ),
    path(
        "objectives/<int:pk>/",
        views.ObjectiveDetailView.as_view(),
        name="objective_detail",
    ),
    path(
        "objectives/<int:pk>/edit/",
        views.ObjectiveUpdateView.as_view(),
        name="objective_update",
    ),
    path(
        "objectives/<int:pk>/delete/",
        views.ObjectiveDeleteView.as_view(),
        name="objective_delete",
    ),

    # --------------------------------------------------------
    # KPIs
    # --------------------------------------------------------
    path(
        "kpis/",
        views.KPIListView.as_view(),
        name="kpi_list",
    ),
    path(
        "kpis/new/",
        views.KPICreateView.as_view(),
        name="kpi_create",
    ),
    path(
        "kpis/<int:pk>/",
        views.KPIDetailView.as_view(),
        name="kpi_detail",
    ),
    path(
        "kpis/<int:pk>/edit/",
        views.KPIUpdateView.as_view(),
        name="kpi_update",
    ),
    path(
        "kpis/<int:pk>/delete/",
        views.KPIDeleteView.as_view(),
        name="kpi_delete",
    ),

    # --------------------------------------------------------
    # Tasks
    # --------------------------------------------------------
    path(
        "tasks/",
        views.TaskListView.as_view(),
        name="task_list",
    ),
    path(
        "tasks/new/",
        views.TaskCreateView.as_view(),
        name="task_create",
    ),
    path(
        "tasks/<int:pk>/",
        views.TaskDetailView.as_view(),
        name="task_detail",
    ),
    path(
        "tasks/<int:pk>/edit/",
        views.TaskUpdateView.as_view(),
        name="task_update",
    ),
    path(
        "tasks/<int:pk>/delete/",
        views.TaskDeleteView.as_view(),
        name="task_delete",
    ),
]
