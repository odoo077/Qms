# hr/views/__init__.py

# Employees
from .employees import (
    EmployeeListView,
    EmployeeCreateView,
    EmployeeUpdateView,
    EmployeeDetailView,
    EmployeeDeleteView,
)

# Departments
from .departments import (
    DepartmentListView,
    DepartmentCreateView,
    DepartmentUpdateView,
    DepartmentDetailView,
    DepartmentDeleteView,
)

# Jobs
from .jobs import (
    JobListView,
    JobCreateView,
    JobUpdateView,
    JobDetailView,
    JobDeleteView,
)

# Work Locations
from .work_locations import (
    WorkLocationListView,
    WorkLocationCreateView,
    WorkLocationUpdateView,
    WorkLocationDetailView,
    WorkLocationDeleteView,
)

# Employee Categories
from .categories import (
    CategoryListView,
    CategoryCreateView,
    CategoryUpdateView,
    CategoryDetailView,
    CategoryDeleteView,
)

# Contract Types
from .contract_types import (
    ContractTypeListView,
    ContractTypeCreateView,
    ContractTypeUpdateView,
    ContractTypeDeleteView,
)

__all__ = [
    # Employees
    "EmployeeListView",
    "EmployeeCreateView",
    "EmployeeUpdateView",
    "EmployeeDetailView",
    "EmployeeDeleteView",

    # Departments
    "DepartmentListView",
    "DepartmentCreateView",
    "DepartmentUpdateView",
    "DepartmentDetailView",
    "DepartmentDeleteView",

    # Jobs
    "JobListView",
    "JobCreateView",
    "JobUpdateView",
    "JobDetailView",
    "JobDeleteView",

    # Work Locations
    "WorkLocationListView",
    "WorkLocationCreateView",
    "WorkLocationUpdateView",
    "WorkLocationDetailView",
    "WorkLocationDeleteView",

    # Employee Categories
    "CategoryListView",
    "CategoryCreateView",
    "CategoryUpdateView",
    "CategoryDetailView",
    "CategoryDeleteView",

    # Contract Types
    "ContractTypeListView",
    "ContractTypeCreateView",
    "ContractTypeUpdateView",
    "ContractTypeDeleteView",
]
