# hr/urls.py
"""
HR application URL configuration (Odoo-like).

Structure principles:
- Clear resource-based grouping (departments / jobs / employees)
- REST-style URLs
- Consistent naming for reverse() and templates
- No business logic here (routing only)
"""

from django.urls import path
from . import views
from .views import JobEmployeeUpdateView, JobDetailView

app_name = "hr"

urlpatterns = [

    # ==========================================================
    # Departments
    # ==========================================================
    path(
        "departments/",
        views.DepartmentListView.as_view(),
        name="department_list",
    ),
    path(
        "departments/new/",
        views.DepartmentCreateView.as_view(),
        name="department_create",
    ),
    path(
        "departments/<int:pk>/",
        views.DepartmentDetailView.as_view(),
        name="department_detail",
    ),
    path(
        "departments/<int:pk>/edit/",
        views.DepartmentUpdateView.as_view(),
        name="department_edit",
    ),

    # ==========================================================
    # Jobs
    # ==========================================================
    path(
        "jobs/",
        views.JobListView.as_view(),
        name="job_list",
    ),
    path(
        "jobs/new/",
        views.JobCreateView.as_view(),
        name="job_create",
    ),
    path(
        "jobs/<int:pk>/",
        views.JobDetailView.as_view(),
        name="job_detail",
    ),
    path(
        "jobs/<int:pk>/edit/",
        views.JobUpdateView.as_view(),
        name="job_edit",
    ),
    path(
        "employees/<int:pk>/change-job/",
        JobEmployeeUpdateView.as_view(),
        name="employee_change_job",
    ),

    # ==========================================================
    # Ajax (HTMX)
    # ==========================================================
    path(
        "ajax/departments/options/",
        views.AjaxDepartmentOptionsView.as_view(),
        name="ajax_department_options",
    ),

    # ==========================================================
    # Employees
    # ==========================================================
    path(
        "employees/",
        views.EmployeeListView.as_view(),
        name="employee_list",
    ),
    path(
        "employees/new/",
        views.EmployeeCreateView.as_view(),
        name="employee_create",
    ),
    path(
        "employees/<int:pk>/",
        views.EmployeeDetailView.as_view(),
        name="employee_detail",
    ),
    path(
        "employees/<int:pk>/edit/",
        views.EmployeeUpdateView.as_view(),
        name="employee_edit",
    ),
    path(
        "employees/bulk/",
        views.EmployeeBulkActionView.as_view(),
        name="employee_bulk",
    ),
]
