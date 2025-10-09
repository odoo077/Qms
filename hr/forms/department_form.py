from django import forms
from django.core.exceptions import ValidationError
from ..models import Department, Employee
from .base import TailwindModelForm


class DepartmentForm(TailwindModelForm):
    class Meta:
        model = Department
        fields = ["active", "name", "company", "parent", "manager", "note", "color"]

    def clean(self):
        cleaned = super().clean()
        company = cleaned.get("company")
        parent = cleaned.get("parent")
        manager: Employee = cleaned.get("manager")

        if parent and not company:
            cleaned["company"] = parent.company
            company = cleaned["company"]

        if company:
            if parent and parent.company_id != company.id:
                raise ValidationError({"parent": "Parent must belong to the same company."})
            if manager and manager.company_id != company.id:
                raise ValidationError({"manager": "Manager must belong to the same company."})

        return cleaned
