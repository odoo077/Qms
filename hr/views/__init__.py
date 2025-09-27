# hr/views/__init__.py
from .employees import (
    EmployeeListView, EmployeeCreateView, EmployeeUpdateView,
    EmployeeDetailView, EmployeeDeleteView,
)
from .departments import (
    DepartmentListView, DepartmentCreateView, DepartmentUpdateView,
    DepartmentDetailView, DepartmentDeleteView,
)
from .jobs import (
    JobListView, JobCreateView, JobUpdateView,
    JobDetailView, JobDeleteView,
)
from .work_locations import (
    WorkLocationListView, WorkLocationCreateView, WorkLocationUpdateView,
    WorkLocationDetailView, WorkLocationDeleteView,
)
from .categories import (
    CategoryListView, CategoryCreateView, CategoryUpdateView,
    CategoryDetailView, CategoryDeleteView,
)
from .contract_types import (
    ContractTypeListView, ContractTypeCreateView, ContractTypeUpdateView,
    ContractTypeDetailView, ContractTypeDeleteView,
)
