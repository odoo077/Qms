# -*- coding: utf-8 -*-
from django import forms
from django.core.exceptions import ValidationError

from .base import CompanyScopedFormMixin, TailwindFormMixin
from ..models.evaluation_template import EvaluationTemplate
from ..models.evaluation_parameter import EvaluationParameter

class EvaluationTemplateForm(CompanyScopedFormMixin, TailwindFormMixin, forms.ModelForm):
    """
    فورم قالب التقييم:
    - لا تحققات معقدة هنا، مجرد دعم لتقييد الشركة إن لزم.
    """
    class Meta:
        model = EvaluationTemplate
        fields = ["company", "name", "description", "active"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class EvaluationParameterInlineFormSet(forms.BaseInlineFormSet):
    """
    فورم سِت لباراميترات القالب:
    - يتحقق أن مجموع الأوزان = 100% (قابل للتغيير إلى ≤ 100%)
    - يتحقق min/max والمنطق مع default لكل صف
    """
    require_total_exact = True

    def clean(self):
        super().clean()
        total = 0.0
        for form in self.forms:
            if not getattr(form, "cleaned_data", None) or form.cleaned_data.get("DELETE", False):
                continue

            weight = float(form.cleaned_data.get("weight_pct") or 0)
            total += weight

            min_score = form.cleaned_data.get("min_score_pct")
            max_score = form.cleaned_data.get("max_score_pct")
            default_score = form.cleaned_data.get("manual_default_score_pct")

            # تحقق النطاق
            if min_score is not None and max_score is not None and min_score > max_score:
                form.add_error("min_score_pct", "Min score cannot be greater than max score.")
            if default_score is not None:
                if min_score is not None and default_score < min_score:
                    form.add_error("manual_default_score_pct", "Default score must be >= min score.")
                if max_score is not None and default_score > max_score:
                    form.add_error("manual_default_score_pct", "Default score must be <= max score.")

        if self.require_total_exact:
            if round(total, 4) != 100.0:
                raise ValidationError("Total parameter weights must equal 100%.")
        else:
            if total > 100:
                raise ValidationError("Total parameter weights cannot exceed 100%.")
