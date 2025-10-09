# -*- coding: utf-8 -*-
from django import forms
from django.core.exceptions import ValidationError

from .base import CompanyScopedFormMixin, TailwindFormMixin
from ..models.task import Task

class TaskForm(CompanyScopedFormMixin, TailwindFormMixin, forms.ModelForm):
    """
    فورم المهمة:
    - نسبة الإنجاز بين 0 و 100
    - توافق الشركة بين company و (objective/kpi/assignee)
    - إذا تم اختيار KPI مربوط بهدف فيجب أن يطابق الحقل objective
    """
    class Meta:
        model = Task
        fields = [
            "company", "objective", "kpi", "title", "description",
            "assignee", "status", "percent_complete", "due_date", "active",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "due_date": forms.DateInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # تقييد الحقول على الشركة إن وُجدت
        if self.company:
            for fname in ("objective", "kpi", "assignee"):
                if fname in self.fields and getattr(self.fields[fname], "queryset", None):
                    try:
                        self.fields[fname].queryset = self.fields[fname].queryset.filter(
                            company_id=getattr(self.company, "id", self.company)
                        )
                    except Exception:
                        pass

    def clean(self):
        cleaned = super().clean()
        percent = cleaned.get("percent_complete")
        company = cleaned.get("company")
        objective = cleaned.get("objective")
        kpi = cleaned.get("kpi")
        assignee = cleaned.get("assignee")

        # نسبة الإنجاز
        if percent is not None and not (0 <= percent <= 100):
            raise ValidationError({"percent_complete": "Percent must be between 0 and 100."})

        # توافق الشركة
        if company:
            if objective and getattr(objective, "company_id", None) != company.id:
                raise ValidationError({"objective": "Objective must belong to the same company."})
            if kpi and getattr(kpi, "company_id", None) != company.id:
                raise ValidationError({"kpi": "KPI must belong to the same company."})
            if assignee and getattr(assignee, "company_id", None) not in (None, company.id):
                raise ValidationError({"assignee": "Assignee must belong to the same company."})

        # تطابق KPI مع الهدف
        if kpi and objective and getattr(kpi, "objective_id", None) != getattr(objective, "id", None):
            raise ValidationError({"kpi": "KPI must belong to the selected Objective."})

        return cleaned
