# -*- coding: utf-8 -*-
from django import forms
from django.core.exceptions import ValidationError

from .base import CompanyScopedFormMixin, TailwindFormMixin
from ..models.objective import Objective

class ObjectiveForm(CompanyScopedFormMixin, TailwindFormMixin, forms.ModelForm):
    """
    فورم هدف (Objective) مع تحققات أساسية:
    - التواريخ: النهاية ≥ البداية
    - الوزن بين 0 و 100
    - فلترة reviewer على شركة الفورم إن وُجدت
    """
    class Meta:
        model = Objective
        fields = [
            "company", "code", "title", "description", "status",
            "date_start", "date_end", "weight_pct", "reviewer", "active",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "date_start": forms.DateInput(),
            "date_end": forms.DateInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # تقييد reviewer على نفس الشركة إن تم تمرير company
        if self.company and "reviewer" in self.fields and getattr(self.fields["reviewer"], "queryset", None):
            try:
                self.fields["reviewer"].queryset = self.fields["reviewer"].queryset.filter(
                    company_id=getattr(self.company, "id", self.company)
                )
            except Exception:
                pass

    def clean(self):
        cleaned = super().clean()
        date_start = cleaned.get("date_start")
        date_end = cleaned.get("date_end")
        weight_pct = cleaned.get("weight_pct")

        # تحقق التواريخ
        if date_start and date_end and date_end < date_start:
            raise ValidationError({"date_end": "End date must be greater than or equal to start date."})

        # تحقق الوزن
        if weight_pct is not None and not (0 <= weight_pct <= 100):
            raise ValidationError({"weight_pct": "Weight must be between 0 and 100."})
        return cleaned


class KPIWeightInlineFormSet(forms.BaseInlineFormSet):
    """
    فورم سِت لمؤشرات KPI ضمن الهدف:
    - يتحقق أن مجموع الأوزان = 100% (يمكن جعله ≤ 100% بتعديل المتغير أدناه)
    """
    require_total_exact = True

    def clean(self):
        super().clean()
        total = 0.0
        for form in self.forms:
            if not getattr(form, "cleaned_data", None) or form.cleaned_data.get("DELETE", False):
                continue
            total += float(form.cleaned_data.get("weight_pct") or 0)
        if self.require_total_exact:
            if round(total, 4) != 100.0:
                raise ValidationError("Total KPI weights must equal 100%.")
        else:
            if total > 100:
                raise ValidationError("Total KPI weights cannot exceed 100%.")
