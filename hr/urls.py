# hr/urls.py
from django.urls import path

# Employees
from .views.employees import (
    EmployeeListView, EmployeeCreateView, EmployeeDetailView,
    EmployeeUpdateView, EmployeeDeleteView,
)

# Departments
from .views.departments import (
    DepartmentListView, DepartmentCreateView, DepartmentDetailView,
    DepartmentUpdateView, DepartmentDeleteView,
)

# Jobs
from .views.jobs import (
    JobListView, JobCreateView, JobDetailView,
    JobUpdateView, JobDeleteView,
)

# Work Locations
from .views.work_locations import (
    WorkLocationListView, WorkLocationCreateView, WorkLocationDetailView,
    WorkLocationUpdateView, WorkLocationDeleteView,
)

# Employee Categories
from .views.categories import (
    CategoryListView, CategoryCreateView, CategoryDetailView,
    CategoryUpdateView, CategoryDeleteView,
)

# Contract Types
from .views.contract_types import (
    ContractTypeListView, ContractTypeCreateView, ContractTypeDetailView,
    ContractTypeUpdateView, ContractTypeDeleteView,
)

app_name = "hr"

urlpatterns = [
    # Employees
    path("employees/", EmployeeListView.as_view(), name="employee_list"),
    path("employees/new/", EmployeeCreateView.as_view(), name="employee_create"),
    path("employees/<int:pk>/", EmployeeDetailView.as_view(), name="employee_detail"),
    path("employees/<int:pk>/edit/", EmployeeUpdateView.as_view(), name="employee_update"),
    path("employees/<int:pk>/delete/", EmployeeDeleteView.as_view(), name="employee_delete"),

    # Departments
    path("departments/", DepartmentListView.as_view(), name="department_list"),
    path("departments/new/", DepartmentCreateView.as_view(), name="department_create"),
    path("departments/<int:pk>/", DepartmentDetailView.as_view(), name="department_detail"),
    path("departments/<int:pk>/edit/", DepartmentUpdateView.as_view(), name="department_update"),
    path("departments/<int:pk>/delete/", DepartmentDeleteView.as_view(), name="department_delete"),

    # Jobs
    path("jobs/", JobListView.as_view(), name="job_list"),
    path("jobs/new/", JobCreateView.as_view(), name="job_create"),
    path("jobs/<int:pk>/", JobDetailView.as_view(), name="job_detail"),
    path("jobs/<int:pk>/edit/", JobUpdateView.as_view(), name="job_update"),
    path("jobs/<int:pk>/delete/", JobDeleteView.as_view(), name="job_delete"),

    # Work Locations
    path("work-locations/", WorkLocationListView.as_view(), name="work_location_list"),
    path("work-locations/new/", WorkLocationCreateView.as_view(), name="work_location_create"),
    path("work-locations/<int:pk>/", WorkLocationDetailView.as_view(), name="work_location_detail"),
    path("work-locations/<int:pk>/edit/", WorkLocationUpdateView.as_view(), name="work_location_update"),
    path("work-locations/<int:pk>/delete/", WorkLocationDeleteView.as_view(), name="work_location_delete"),

    # Employee Categories
    path("categories/", CategoryListView.as_view(), name="category_list"),
    path("categories/new/", CategoryCreateView.as_view(), name="category_create"),
    path("categories/<int:pk>/", CategoryDetailView.as_view(), name="category_detail"),
    path("categories/<int:pk>/edit/", CategoryUpdateView.as_view(), name="category_update"),
    path("categories/<int:pk>/delete/", CategoryDeleteView.as_view(), name="category_delete"),

    # Contract Types
    path("contract-types/", ContractTypeListView.as_view(), name="contract_type_list"),
    path("contract-types/new/", ContractTypeCreateView.as_view(), name="contract_type_create"),
    path("contract-types/<int:pk>/", ContractTypeDetailView.as_view(), name="contract_type_detail"),
    path("contract-types/<int:pk>/edit/", ContractTypeUpdateView.as_view(), name="contract_type_update"),
    path("contract-types/<int:pk>/delete/", ContractTypeDeleteView.as_view(), name="contract_type_delete"),
]
