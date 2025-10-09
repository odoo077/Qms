# -*- coding: utf-8 -*-
from django import forms
from django.core.exceptions import ValidationError

from .base import CompanyScopedFormMixin, TailwindFormMixin
from ..models.evaluation import Evaluation

class EvaluationForm(CompanyScopedFormMixin, TailwindFormMixin, forms.ModelForm):
    """
    فورم التقييم:
    - التواريخ منطقية (النهاية ≥ البداية)
    - توافق الشركة بين company و (employee/evaluator/template)
    """
    class Meta:
        model = Evaluation
        fields = [
            "company", "employee", "evaluator",
            "date_start", "date_end", "template",
            "final_score_pct", "overall_rating", "calibration_notes",
            "active",
        ]
        widgets = {
            "calibration_notes": forms.Textarea(attrs={"rows": 3}),
            "date_start": forms.DateInput(),
            "date_end": forms.DateInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # تقييد الحقول بالاعتماد على الشركة إن تم تمريرها
        if self.company:
            for fname in ("employee", "evaluator", "template"):
                if fname in self.fields and getattr(self.fields[fname], "queryset", None):
                    try:
                        self.fields[fname].queryset = self.fields[fname].queryset.filter(
                            company_id=getattr(self.company, "id", self.company)
                        )
                    except Exception:
                        pass

    def clean(self):
        cleaned = super().clean()
        ds = cleaned.get("date_start")
        de = cleaned.get("date_end")
        company = cleaned.get("company")
        employee = cleaned.get("employee")
        evaluator = cleaned.get("evaluator")
        template = cleaned.get("template")

        # تحقق التواريخ
        if ds and de and de < ds:
            raise ValidationError({"date_end": "End date must be greater than or equal to start date."})

        # توافق الشركة
        if company:
            if employee and getattr(employee, "company_id", None) not in (None, company.id):
                raise ValidationError({"employee": "Employee must belong to the same company."})
            if evaluator and getattr(evaluator, "company_id", None) not in (None, company.id):
                raise ValidationError({"evaluator": "Evaluator must belong to the same company."})
            if template and getattr(template, "company_id", None) not in (None, company.id):
                raise ValidationError({"template": "Template must belong to the same company."})

        return cleaned


class EvaluationParameterResultInlineFormSet(forms.BaseInlineFormSet):
    """
    فورم سِت لنتائج الباراميترات ضمن التقييم:
    - يتحقق أن score_pct ضمن نطاق (min/max) للباراميتر المرتبط إن وُجد.
    """
    def clean(self):
        super().clean()
        for form in self.forms:
            if not getattr(form, "cleaned_data", None) or form.cleaned_data.get("DELETE", False):
                continue

            param = form.cleaned_data.get("parameter")
            score = form.cleaned_data.get("score_pct")

            if param and score is not None:
                min_score = getattr(param, "min_score_pct", None)
                max_score = getattr(param, "max_score_pct", None)
                if min_score is not None and score < min_score:
                    form.add_error("score_pct", "Score is below the parameter minimum.")
                if max_score is not None and score > max_score:
                    form.add_error("score_pct", "Score is above the parameter maximum.")
