# -*- coding: utf-8 -*-
from django import forms
from django.core.exceptions import ValidationError

from .base import CompanyScopedFormMixin, TailwindFormMixin
from ..models.evaluation_parameter import EvaluationParameter

class EvaluationParameterForm(CompanyScopedFormMixin, TailwindFormMixin, forms.ModelForm):
    """
    فورم باراميتر التقييم:
    - الوزن بين 0 و 100
    - تحقق min/max والمنطق مع default
    - توافق الشركة بين template و (objective/kpi) إن وُجدت
    """
    class Meta:
        model = EvaluationParameter
        fields = [
            "template", "name", "code", "source_kind",
            "objective", "kpi",
            "external_model", "external_field", "external_aggregation", "external_filter",
            "manual_default_score_pct", "min_score_pct", "max_score_pct",
            "weight_pct",
        ]
        widgets = {
            "external_filter": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # يمكن تقييد objective/kpi لاحقًا بحسب الشركة من الـ View إن رغبت

    def clean(self):
        cleaned = super().clean()
        weight = cleaned.get("weight_pct")
        min_score = cleaned.get("min_score_pct")
        max_score = cleaned.get("max_score_pct")
        default_score = cleaned.get("manual_default_score_pct")
        template = cleaned.get("template")
        objective = cleaned.get("objective")
        kpi = cleaned.get("kpi")

        # الوزن
        if weight is not None and not (0 <= weight <= 100):
            raise ValidationError({"weight_pct": "Weight must be between 0 and 100."})

        # نطاق الدرجات
        if min_score is not None and max_score is not None and min_score > max_score:
            raise ValidationError({"min_score_pct": "Min score cannot be greater than max score."})
        if default_score is not None:
            if min_score is not None and default_score < min_score:
                raise ValidationError({"manual_default_score_pct": "Default score must be >= min score."})
            if max_score is not None and default_score > max_score:
                raise ValidationError({"manual_default_score_pct": "Default score must be <= max score."})

        # توافق الشركة (إن توفرت على القيم المرتبطة)
        tmpl_company_id = getattr(template, "company_id", None) if template else None
        if tmpl_company_id:
            if objective and getattr(objective, "company_id", None) not in (None, tmpl_company_id):
                raise ValidationError({"objective": "Objective must belong to the template company."})
            if kpi and getattr(kpi, "company_id", None) not in (None, tmpl_company_id):
                raise ValidationError({"kpi": "KPI must belong to the template company."})

        return cleaned
