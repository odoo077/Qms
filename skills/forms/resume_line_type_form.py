from django import forms
from skills.models import HrResumeLineType
from .base import TailwindModelForm


class ResumeLineTypeForm(TailwindModelForm):
    class Meta:
        model = HrResumeLineType
        fields = ["active", "name", "sequence", "is_course", "properties_definition"]
        widgets = {
            "properties_definition": forms.Textarea(attrs={"rows": 6, "placeholder": '{"fields":[{"name":"hours","type":"int","required":false}]}'})
        }
