from django import forms
from django.core.exceptions import ValidationError
from skills.models import HrResumeLine, HrResumeLineType
from .base import TailwindModelForm


class ResumeLineForm(TailwindModelForm):
    """
    سطر في السيرة الذاتية:
    - يحترم المنطق: لو course_type != "external" يمسح external_url.
    - يتأكد من تاريخ البداية/النهاية في clean() (الموديل يفعل ذلك أيضًا).
    """
    class Meta:
        model = HrResumeLine
        fields = [
            "employee",
            "name",
            "line_type",
            "date_start",
            "date_end",
            "description",
            "course_type",
            "external_url",
            "certificate_file",
            # اختياري: "properties" إن أردت تحرير JSON من الواجهة
        ]
        widgets = {
            "date_start": forms.DateInput(attrs={"type": "date"}),
            "date_end": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 5, "placeholder": "Details (HTML allowed if your widget supports it)"}),
            "external_url": forms.URLInput(attrs={"placeholder": "https://..."}),
        }

    def clean(self):
        cleaned = super().clean()
        ct = cleaned.get("course_type")
        url = cleaned.get("external_url")

        if ct != "external" and url:
            # النموذج يمسح الرابط عند الحفظ أيضًا، لكن ننبّه هنا للمستخدم
            cleaned["external_url"] = ""
        return cleaned
