# hr/forms.py
from django import forms
from .models import Department, Job , Employee


class DepartmentForm(forms.ModelForm):
    class Meta:
        model  = Department
        fields = ("name", "company", "parent", "manager", "active")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # حدّ parent على نفس الشركة + استبعد نفسك
        company = self.initial.get("company") or getattr(self.instance, "company", None)
        qs = Department.objects.all()
        if company:
            qs = qs.filter(company=company)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        self.fields["parent"].queryset = qs

    def clean(self):
        cleaned = super().clean()
        parent  = cleaned.get("parent")
        company = cleaned.get("company")
        if parent and company and parent.company_id != company.id:
            self.add_error("parent", "Parent department must belong to the same company.")
        return cleaned


class JobForm(forms.ModelForm):
    class Meta:
        model = Job
        fields = ("name", "company", "department", "description", "active")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        company = self.initial.get("company") or getattr(self.instance, "company", None)
        qs = Job.objects.all()
        if company:
            self.fields["department"].queryset = self.fields["department"].queryset.filter(company=company)



class EmployeeForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = ("name", "company", "department", "job", "active")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        company = self.initial.get("company") or getattr(self.instance, "company", None)
        if company:
            self.fields["department"].queryset = self.fields["department"].queryset.filter(company=company)
            self.fields["job"].queryset = self.fields["job"].queryset.filter(company=company)
