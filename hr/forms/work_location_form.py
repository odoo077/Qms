from django import forms
from django.core.exceptions import ValidationError
from ..models import WorkLocation
from .base import TailwindModelForm


class WorkLocationForm(TailwindModelForm):
    class Meta:
        model = WorkLocation
        fields = ["active", "name", "company", "location_type", "address", "location_number"]

    def clean(self):
        cleaned = super().clean()
        company = cleaned.get("company")
        address = cleaned.get("address")

        if company and address and getattr(address, "company_id", None) and address.company_id != company.id:
            raise ValidationError({"address": "Address must belong to the same company."})

        return cleaned
