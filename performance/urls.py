# -*- coding: utf-8 -*-
# performance/urls.py
# مسارات تطبيق الأداء؛ كل View مرتبطة بصفحات القائمة/التفاصيل/الإنشاء/التعديل/الحذف

from django.urls import path

# Objectives
from .views.objectives import (
    ObjectiveListView,
    ObjectiveDetailView,
    ObjectiveCreateView,
    ObjectiveUpdateView,
    ObjectiveDeleteView,
)

# KPIs
from .views.kpis import (
    KPIListView,
    KPIDetailView,
    KPICreateView,
    KPIUpdateView,
    KPIDeleteView,
)

# Tasks
from .views.tasks import (
    TaskListView,
    TaskDetailView,
    TaskCreateView,
    TaskUpdateView,
    TaskDeleteView,
)

# Evaluation Templates
from .views.templates import (
    EvaluationTemplateListView,
    EvaluationTemplateDetailView,
    EvaluationTemplateCreateView,
    EvaluationTemplateUpdateView,
    EvaluationTemplateDeleteView,
)

# Evaluation Parameters
from .views.parameters import (
    EvaluationParameterListView,
    EvaluationParameterDetailView,
    EvaluationParameterCreateView,
    EvaluationParameterUpdateView,
    EvaluationParameterDeleteView,
)

# Evaluations
from .views.evaluations import (
    EvaluationListView,
    EvaluationDetailView,
    EvaluationCreateView,
    EvaluationUpdateView,
    EvaluationDeleteView,
)

# Assignments: Departments
from .views.assignment_departments import (
    ObjectiveDepartmentAssignmentListView,
    ObjectiveDepartmentAssignmentCreateView,
    ObjectiveDepartmentAssignmentUpdateView,
    ObjectiveDepartmentAssignmentDeleteView,
)

# Assignments: Employees
from .views.assignment_employees import (
    ObjectiveEmployeeAssignmentListView,
    ObjectiveEmployeeAssignmentCreateView,
    ObjectiveEmployeeAssignmentUpdateView,
    ObjectiveEmployeeAssignmentDeleteView,
)

# Bulk + Rebuild (optional)
from .views.assignment_bulk import (
    ObjectiveEmployeeBulkAssignView,
    ObjectiveRebuildParticipantsView,
)

app_name = "performance"

urlpatterns = [
    # Objectives
    path("objectives/", ObjectiveListView.as_view(), name="objective_list"),
    path("objectives/create/", ObjectiveCreateView.as_view(), name="objective_create"),
    path("objectives/<int:pk>/", ObjectiveDetailView.as_view(), name="objective_detail"),
    path("objectives/<int:pk>/edit/", ObjectiveUpdateView.as_view(), name="objective_update"),
    path("objectives/<int:pk>/delete/", ObjectiveDeleteView.as_view(), name="objective_delete"),

    # KPIs
    path("kpis/", KPIListView.as_view(), name="kpi_list"),
    path("kpis/create/", KPICreateView.as_view(), name="kpi_create"),
    path("kpis/<int:pk>/", KPIDetailView.as_view(), name="kpi_detail"),
    path("kpis/<int:pk>/edit/", KPIUpdateView.as_view(), name="kpi_update"),
    path("kpis/<int:pk>/delete/", KPIDeleteView.as_view(), name="kpi_delete"),

    # Tasks
    path("tasks/", TaskListView.as_view(), name="task_list"),
    path("tasks/create/", TaskCreateView.as_view(), name="task_create"),
    path("tasks/<int:pk>/", TaskDetailView.as_view(), name="task_detail"),
    path("tasks/<int:pk>/edit/", TaskUpdateView.as_view(), name="task_update"),
    path("tasks/<int:pk>/delete/", TaskDeleteView.as_view(), name="task_delete"),

    # Evaluation Templates
    path("templates/", EvaluationTemplateListView.as_view(), name="evaluation_template_list"),
    path("templates/create/", EvaluationTemplateCreateView.as_view(), name="evaluation_template_create"),
    path("templates/<int:pk>/", EvaluationTemplateDetailView.as_view(), name="evaluation_template_detail"),
    path("templates/<int:pk>/edit/", EvaluationTemplateUpdateView.as_view(), name="evaluation_template_update"),
    path("templates/<int:pk>/delete/", EvaluationTemplateDeleteView.as_view(), name="evaluation_template_delete"),

    # Evaluation Parameters
    path("parameters/", EvaluationParameterListView.as_view(), name="evaluation_parameter_list"),
    path("parameters/create/", EvaluationParameterCreateView.as_view(), name="evaluation_parameter_create"),
    path("parameters/<int:pk>/", EvaluationParameterDetailView.as_view(), name="evaluation_parameter_detail"),
    path("parameters/<int:pk>/edit/", EvaluationParameterUpdateView.as_view(), name="evaluation_parameter_update"),
    path("parameters/<int:pk>/delete/", EvaluationParameterDeleteView.as_view(), name="evaluation_parameter_delete"),

    # Evaluations
    path("evaluations/", EvaluationListView.as_view(), name="evaluation_list"),
    path("evaluations/create/", EvaluationCreateView.as_view(), name="evaluation_create"),
    path("evaluations/<int:pk>/", EvaluationDetailView.as_view(), name="evaluation_detail"),
    path("evaluations/<int:pk>/edit/", EvaluationUpdateView.as_view(), name="evaluation_update"),
    path("evaluations/<int:pk>/delete/", EvaluationDeleteView.as_view(), name="evaluation_delete"),

    # Department assignments
    path("objectives/<int:pk>/assignments/departments/", ObjectiveDepartmentAssignmentListView.as_view(),
         name="objective_department_assignment_list"),
    path("objectives/<int:pk>/assignments/departments/create/", ObjectiveDepartmentAssignmentCreateView.as_view(),
         name="objective_department_assignment_create"),
    path("objectives/<int:pk>/assignments/departments/<int:assignment_pk>/edit/",
         ObjectiveDepartmentAssignmentUpdateView.as_view(), name="objective_department_assignment_update"),
    path("objectives/<int:pk>/assignments/departments/<int:assignment_pk>/delete/",
         ObjectiveDepartmentAssignmentDeleteView.as_view(), name="objective_department_assignment_delete"),

    # Employee assignments
    path("objectives/<int:pk>/assignments/employees/", ObjectiveEmployeeAssignmentListView.as_view(),
         name="objective_employee_assignment_list"),
    path("objectives/<int:pk>/assignments/employees/create/", ObjectiveEmployeeAssignmentCreateView.as_view(),
         name="objective_employee_assignment_create"),
    path("objectives/<int:pk>/assignments/employees/<int:assignment_pk>/edit/",
         ObjectiveEmployeeAssignmentUpdateView.as_view(), name="objective_employee_assignment_update"),
    path("objectives/<int:pk>/assignments/employees/<int:assignment_pk>/delete/",
         ObjectiveEmployeeAssignmentDeleteView.as_view(), name="objective_employee_assignment_delete"),

    # Bulk assign + rebuild (optional)
    path("objectives/<int:pk>/assignments/employees/bulk/", ObjectiveEmployeeBulkAssignView.as_view(),
         name="objective_employee_assignment_bulk"),
    path("objectives/<int:pk>/participants/rebuild/", ObjectiveRebuildParticipantsView.as_view(),
         name="objective_rebuild_participants"),
]
