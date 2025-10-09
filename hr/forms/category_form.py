from ..models import EmployeeCategory
from .base import TailwindModelForm


class EmployeeCategoryForm(TailwindModelForm):
    class Meta:
        model = EmployeeCategory
        fields = ["name", "color"]
