from django import forms
from skills.models.resume_line import HrResumeLine
from skills.models.resume_line_type import HrResumeLineType

class ResumeLineForm(forms.ModelForm):
    class Meta:
        model = HrResumeLine
        fields = ["employee", "name", "line_type", "date_start", "date_end", "description", "external_url", "certificate_file"]

class ResumeLineTypeForm(forms.ModelForm):
    class Meta:
        model = HrResumeLineType
        fields = ["name", "sequence", "is_course"]
