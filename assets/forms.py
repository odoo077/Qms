# assets/forms.py
from __future__ import annotations
from typing import Any, Dict

from django import forms
from django.contrib.auth import get_user_model

from base.company_context import get_company_id as get_current_company
from base.models import Company
from . import models as m

User = get_user_model()


class _ScopedModelForm(forms.ModelForm):
    """
    يمرَّر إليها request من الـView لتقييد الـquerysets على الشركات المسموح بها
    وتعيين الشركة الحالية كقيمة افتراضية.
    """
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

        # الشركات المسموح بها (حسب ACL)
        allowed_companies = Company.objects.with_acl("view")
        self.fields.get("company", forms.Field()).queryset = allowed_companies

        # اجعل الشركة الحالية افتراضية إن كانت ضمن المسموح
        cur = get_current_company(self.request)
        if cur and "company" in self.fields and allowed_companies.filter(pk=cur.pk).exists():
            if not self.instance.pk:
                self.fields["company"].initial = cur

    def _filter_by_company(self, field_name: str, model_qs):
        if field_name not in self.fields:
            return
        company_id = None
        if "company" in self.fields:
            # قيمة الشركة من initial أو instance
            company_id = (self.data.get(self.add_prefix("company"))
                          or self.initial.get("company")
                          or getattr(self.instance, "company_id", None))
        if company_id:
            self.fields[field_name].queryset = model_qs.filter(company_id=company_id)
        else:
            # إن لم تُحدَّد شركة بعد، اكتفِ بتقييد عام على الشركات المسموح بها
            self.fields[field_name].queryset = model_qs.filter(
                company_id__in=Company.objects.with_acl("view").values("id")
            )


class AssetCategoryForm(_ScopedModelForm):
    class Meta:
        model = m.AssetCategory
        fields = ["name", "company", "parent", "active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._filter_by_company("parent", m.AssetCategory.objects.all())


class AssetForm(_ScopedModelForm):
    class Meta:
        model = m.Asset
        fields = [
            "name", "code", "serial",
            "company", "category", "department", "holder",
            "status", "purchase_date", "purchase_value",
            "note", "parent", "active",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._filter_by_company("category", m.AssetCategory.objects.all())
        # department/holder تعود لموديولات HR
        from hr.models import Department, Employee
        self._filter_by_company("department", Department.objects.all())
        self._filter_by_company("holder", Employee.objects.all())
        self._filter_by_company("parent", m.Asset.objects.all())


class AssetAssignmentForm(_ScopedModelForm):
    class Meta:
        model = m.AssetAssignment
        fields = ["asset", "employee", "company", "date_from", "date_to", "note", "active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._filter_by_company("asset", m.Asset.objects.all())
        from hr.models import Employee
        self._filter_by_company("employee", Employee.objects.all())
        # company يُملأ تلقائيًا عند الحفظ إن لزم، لكن نُظهره للوضوح فقط.
