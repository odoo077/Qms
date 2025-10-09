# -*- coding: utf-8 -*-
from django import forms
from django.core.exceptions import ValidationError

from .base import CompanyScopedFormMixin, TailwindFormMixin
from ..models.objective_employee_assignment import ObjectiveEmployeeAssignment

class ObjectiveEmployeeAssignmentForm(CompanyScopedFormMixin, TailwindFormMixin, forms.ModelForm):
    """
    فورم تعيين هدف على موظف:
    - تقييد القوائم على الشركة الممررة (objective/employee)
    - منع التكرار (objective + employee)
    - تحقق من توافق الشركة بين الهدف والموظف
    """
    class Meta:
        model = ObjectiveEmployeeAssignment
        fields = ["objective", "employee"]

    def __init__(self, *args, **kwargs):
        # نتوقع تمرير company من الـ View
        super().__init__(*args, **kwargs)
        if self.company:
            for fname in ("objective", "employee"):
                if fname in self.fields and getattr(self.fields[fname], "queryset", None):
                    try:
                        self.fields[fname].queryset = self.fields[fname].queryset.filter(
                            company_id=getattr(self.company, "id", self.company)
                        )
                    except Exception:
                        pass

    def clean(self):
        cleaned = super().clean()
        objective = cleaned.get("objective")
        employee = cleaned.get("employee")

        # تحقق الشركة
        if objective and employee:
            if getattr(objective, "company_id", None) != getattr(employee, "company_id", None):
                raise ValidationError({"employee": "Employee must belong to the same company as Objective."})

        # منع التكرار (نفس الهدف والموظف)
        if objective and employee:
            qs = ObjectiveEmployeeAssignment.objects.all()
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            exists = qs.filter(objective=objective, employee=employee).exists()
            if exists:
                raise ValidationError({"employee": "This employee is already assigned to the objective."})

        return cleaned
