# -*- coding: utf-8 -*-
from django import forms
from django.core.exceptions import ValidationError

from .base import CompanyScopedFormMixin, TailwindFormMixin
from ..models.kpi import KPI

class KPIForm(CompanyScopedFormMixin, TailwindFormMixin, forms.ModelForm):
    """
    فورم KPI:
    - الوزن بين 0 و 100
    - القيم العددية غير سالبة
    - تطابق الشركة بين objective و company
    """
    class Meta:
        model = KPI
        fields = [
            "company", "objective", "name", "description",
            "unit", "higher_is_better",
            "target_value", "baseline_value", "current_value",
            "weight_pct", "active",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # تقييد objective على نفس الشركة إن وُجدت
        if self.company and "objective" in self.fields and getattr(self.fields["objective"], "queryset", None):
            try:
                self.fields["objective"].queryset = self.fields["objective"].queryset.filter(
                    company_id=getattr(self.company, "id", self.company)
                )
            except Exception:
                pass

    def clean(self):
        cleaned = super().clean()
        weight = cleaned.get("weight_pct")
        target = cleaned.get("target_value")
        baseline = cleaned.get("baseline_value")
        current = cleaned.get("current_value")
        company = cleaned.get("company")
        objective = cleaned.get("objective")

        # تحقق الوزن
        if weight is not None and not (0 <= weight <= 100):
            raise ValidationError({"weight_pct": "Weight must be between 0 and 100."})

        # تحقق القيم غير سالبة
        for fname in ("target_value", "baseline_value", "current_value"):
            val = cleaned.get(fname)
            if val is not None and val < 0:
                raise ValidationError({fname: "This value cannot be negative."})

        # توافق الشركة
        if company and objective and getattr(objective, "company_id", None) != company.id:
            raise ValidationError({"objective": "Objective must belong to the same company."})

        return cleaned
