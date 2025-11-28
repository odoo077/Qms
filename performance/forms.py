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
            # على الإنشاء فقط: نضبط الشركة الحالية كقيمة افتراضية
            if not getattr(self.instance, "pk", None):
                self.fields["company"].initial = current

    def _filter_by_company(self, field_name, qs):
        """
        Restrict queryset by selected or allowed companies.
        """
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
# 1. Evaluation Type Form (NEW)
# ===============================================================
class EvaluationTypeForm(_ScopedModelForm):
    class Meta:
        model = m.EvaluationType
        exclude = (
            "id",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        )


# ===============================================================
# 2. Evaluation Approval Step Form (NEW)
# ===============================================================
class EvaluationApprovalStepForm(_ScopedModelForm):
    class Meta:
        model = m.EvaluationApprovalStep
        exclude = (
            "id",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from hr.models import Employee
        # فلترة الحقول المرتبطة بالشركة
        self._filter_by_company("evaluation_type", m.EvaluationType.objects.all())
        self._filter_by_company("approver_employee", Employee.objects.all())


# ===============================================================
# 3. Evaluation Parameter Form
# ===============================================================
class EvaluationParameterForm(_ScopedModelForm):
    class Meta:
        model = m.EvaluationParameter
        exclude = (
            "id",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        )


# ===============================================================
# 4. Evaluation Template Form
# ===============================================================
class EvaluationTemplateForm(_ScopedModelForm):
    class Meta:
        model = m.EvaluationTemplate
        exclude = (
            "id",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
            "company",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._filter_by_company("parameters", m.EvaluationParameter.objects.all())


# ===============================================================
# 5. Evaluation Form
# ===============================================================
class EvaluationForm(_ScopedModelForm):
    class Meta:
        model = m.Evaluation
        exclude = (
            "id",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
            "final_score_pct",
            "state",
            "current_step",
            "current_approver",
            "submitted_at",
            "submitted_by",
            "calibrated_at",
            "calibrated_by",
            "approved_at",
            "approved_by",
            "locked_at",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from hr.models import Employee
        self._filter_by_company("employee", Employee.objects.all())
        self._filter_by_company("evaluator", Employee.objects.all())
        self._filter_by_company("template", m.EvaluationTemplate.objects.all())
        self._filter_by_company("evaluation_type", m.EvaluationType.objects.all())


# ===============================================================
# 6. Objective Form
# ===============================================================
class ObjectiveForm(_ScopedModelForm):
    class Meta:
        model = m.Objective
        exclude = (
            "id",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from hr.models import Department, Employee
        self._filter_by_company("department", Department.objects.all())
        self._filter_by_company("employee", Employee.objects.all())


# ===============================================================
# 7. KPI Form
# ===============================================================
class KPIForm(_ScopedModelForm):
    class Meta:
        model = m.KPI
        exclude = (
            "id",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
            "company",
        )


# ===============================================================
# 8. Task Form
# ===============================================================
class TaskForm(_ScopedModelForm):
    class Meta:
        model = m.Task
        exclude = (
            "id",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
            "company",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from hr.models import Employee
        self._filter_by_company("assignee", Employee.objects.all())
