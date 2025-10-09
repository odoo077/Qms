# -*- coding: utf-8 -*-
from typing import Iterable, List
from django import forms
from django.core.exceptions import ValidationError

from .base import CompanyScopedFormMixin, TailwindFormMixin
from ..models.objective import Objective
from ..models.objective_employee_assignment import ObjectiveEmployeeAssignment

class ObjectiveEmployeeBulkAssignmentForm(CompanyScopedFormMixin, TailwindFormMixin, forms.Form):
    """
    فورم تعيين جماعي لموظفين على هدف:
    - يختار المستخدم Objective واحد
    - يختار مجموعة Employees (MultipleChoice)
    - يمنع التكرار ويعيد عدد المضافين فعليًا
    - لا يقوم ببناء المشاركين هنا (أفضل ممارسات): نفّذ ذلك في الـ View بعد النجاح
    """
    objective = forms.ModelChoiceField(queryset=Objective.objects.none(), label="Objective")
    employees = forms.ModelMultipleChoiceField(queryset=None, label="Employees")

    def __init__(self, *args, **kwargs):
        # نتوقع تمرير company و QuerySet للموظفين (محلّيًا أو من الـ View)
        employees_qs = kwargs.pop("employees_qs", None)
        super().__init__(*args, **kwargs)

        # تقييد الهدف على الشركة
        if self.company:
            self.fields["objective"].queryset = Objective.objects.filter(
                company_id=getattr(self.company, "id", self.company)
            )
        else:
            self.fields["objective"].queryset = Objective.objects.all()

        # تقييد الموظفين على الشركة (إما من employees_qs أو من الحقل نفسه إن كان مرتبطًا بموديل يدعم الشركة)
        if employees_qs is not None:
            self.fields["employees"].queryset = employees_qs
        else:
            self.fields["employees"].queryset = self.fields["employees"].queryset or []

    def clean(self):
        cleaned = super().clean()
        objective = cleaned.get("objective")
        employees = cleaned.get("employees")

        if not objective:
            raise ValidationError({"objective": "Objective is required."})
        if not employees or len(employees) == 0:
            raise ValidationError({"employees": "Select at least one employee."})

        # توافق الشركة (إذا كان employees_qs غير مقيّد قد تأتي قيم من شركات أخرى)
        ocid = getattr(objective, "company_id", None)
        for emp in employees:
            if getattr(emp, "company_id", None) not in (None, ocid):
                raise ValidationError({"employees": "All employees must belong to the objective company."})

        return cleaned

    def save(self) -> int:
        """
        ينشئ التعيينات التي لا توجد مسبقًا فقط.
        يعيد عدد التعيينات الجديدة التي تم إنشاؤها.
        """
        objective = self.cleaned_data["objective"]
        employees = self.cleaned_data["employees"]

        created_count = 0
        existing_pairs = set(
            ObjectiveEmployeeAssignment.objects.filter(objective=objective, employee__in=employees)
            .values_list("employee_id", flat=True)
        )
        to_create = [emp for emp in employees if emp.id not in existing_pairs]

        # إنشاء دفعي (يمكنك التحسين بـ bulk_create)
        objs = [
            ObjectiveEmployeeAssignment(objective=objective, employee=emp)
            for emp in to_create
        ]
        if objs:
            ObjectiveEmployeeAssignment.objects.bulk_create(objs, ignore_conflicts=True)
            created_count = len(objs)
        return created_count
