from django import forms
from django.core.exceptions import ValidationError
from ..models import Job
from .base import TailwindModelForm


class JobForm(TailwindModelForm):
    class Meta:
        model = Job
        fields = [
            "active", "name", "sequence",
            "company", "department", "recruiter", "contract_type",
            "no_of_recruitment", "description", "requirements",
        ]

    def clean(self):
        cleaned = super().clean()
        company = cleaned.get("company")
        department = cleaned.get("department")

        if department and not company:
            cleaned["company"] = department.company
            company = cleaned["company"]

        if company and department and department.company_id != company.id:
            raise ValidationError({"department": "Department must belong to the same company."})

        return cleaned
