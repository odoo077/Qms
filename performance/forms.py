# performance/forms.py
from __future__ import annotations
from django import forms
from base.company_context import get_current_company_object
from base.models import Company
from . import models as m


# ===============================================================
# Scoped Base Form
# ===============================================================
class _ScopedModelForm(forms.ModelForm):
    """
    Base form to restrict company and related foreign keys
    according to ACLs and active company.
    """
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

        allowed_companies = Company.objects.with_acl("view")
        if "company" in self.fields:
            self.fields["company"].queryset = allowed_companies

        current = get_current_company_object()
        if current and "company" in self.fields and allowed_companies.filter(pk=current.pk).exists():
            if not getattr(self.instance, "pk", None):
                self.fields["company"].initial = current

    def _filter_by_company(self, field_name, qs):
        """Restrict queryset by selected or allowed companies"""
        if field_name not in self.fields:
            return
        company_id = (
            self.data.get(self.add_prefix("company"))
            or self.initial.get("company")
            or getattr(self.instance, "company_id", None)
        )
        if company_id:
            self.fields[field_name].queryset = qs.filter(company_id=company_id)
        else:
            self.fields[field_name].queryset = qs.filter(
                company_id__in=Company.objects.with_acl("view").values("id")
            )


# ===============================================================
# 1. Evaluation Parameter Form
# ===============================================================
class EvaluationParameterForm(_ScopedModelForm):
    class Meta:
        model = m.EvaluationParameter
        exclude = ("id", "created_at", "updated_at")


# ===============================================================
# 2. Evaluation Template Form
# ===============================================================
class EvaluationTemplateForm(_ScopedModelForm):
    class Meta:
        model = m.EvaluationTemplate
        exclude = ("id", "created_at", "updated_at", "company")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._filter_by_company("parameters", m.EvaluationParameter.objects.all())


# ===============================================================
# 3. Evaluation Form
# ===============================================================
class EvaluationForm(_ScopedModelForm):
    class Meta:
        model = m.Evaluation
        exclude = ("id", "created_at", "updated_at")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from hr.models import Employee
        self._filter_by_company("employee", Employee.objects.all())
        self._filter_by_company("template", m.EvaluationTemplate.objects.all())


# ===============================================================
# 4. Objective Form
# ===============================================================
class ObjectiveForm(_ScopedModelForm):
    class Meta:
        model = m.Objective
        exclude = ("id", "created_at", "updated_at")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from hr.models import Department, Employee
        self._filter_by_company("department", Department.objects.all())
        self._filter_by_company("employee", Employee.objects.all())


# ===============================================================
# 5. KPI Form
# ===============================================================
class KPIForm(_ScopedModelForm):
    class Meta:
        model = m.KPI
        exclude = ("id", "created_at", "updated_at", "company")


# ===============================================================
# 6. Task Form
# ===============================================================
class TaskForm(_ScopedModelForm):
    class Meta:
        model = m.Task
        exclude = ("id", "created_at", "updated_at", "company")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from hr.models import Employee
        self._filter_by_company("assignee", Employee.objects.all())
