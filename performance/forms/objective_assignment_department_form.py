# -*- coding: utf-8 -*-
from django import forms
from django.core.exceptions import ValidationError

from .base import CompanyScopedFormMixin, TailwindFormMixin
from ..models.objective_department_assignment import ObjectiveDepartmentAssignment

class ObjectiveDepartmentAssignmentForm(CompanyScopedFormMixin, TailwindFormMixin, forms.ModelForm):
    """
    فورم تعيين هدف على قسم:
    - تقييد القوائم على الشركة الممررة (objective/department)
    - منع التكرار (objective + department)
    - تحقق من توافق الشركة بين الهدف والقسم
    - التعامل مع include_children من حيث التداخل المنطقي مع تعيينات أخرى
    """
    class Meta:
        model = ObjectiveDepartmentAssignment
        fields = ["objective", "department", "include_children"]
        widgets = {
            "include_children": forms.CheckboxInput(),
        }

    def __init__(self, *args, **kwargs):
        # نتوقع تمرير company من الـ View
        super().__init__(*args, **kwargs)
        if self.company:
            # تقييد القوائم على الشركة
            for fname in ("objective", "department"):
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
        department = cleaned.get("department")
        include_children = cleaned.get("include_children")

        # تحقق الشركة
        if objective and department:
            if getattr(objective, "company_id", None) != getattr(department, "company_id", None):
                raise ValidationError({"department": "Department must belong to the same company as Objective."})

        # منع التكرار (نفس الهدف والقسم)
        if objective and department:
            qs = ObjectiveDepartmentAssignment.objects.all()
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            exists = qs.filter(objective=objective, department=department).exists()
            if exists:
                raise ValidationError({"department": "This department is already assigned to the objective."})

        # منطق إضافي لـ include_children (اختياري/مثال):
        # يمكن هنا منع إضافة parent مع child مكرر أو العكس، إذا أردت تشددًا أكثر،
        # لكنه يعتمد على بنية شجرة الأقسام لديك.
        # اتركناه كتلميح فقط.

        return cleaned
