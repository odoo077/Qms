# base/forms/partner_forms.py
from django import forms
from ..models import Partner

class PartnerForm(forms.ModelForm):
    class Meta:
        model = Partner
        fields = (
            "name", "is_company", "type", "parent", "company",
            "email", "phone", "website", "vat", "company_registry", "categories",
            "street", "street2", "zip", "city", "state", "country",
        )
