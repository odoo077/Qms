# payroll/forms.py

from django import forms
from . import models as m


# ============================================================
# Configuration / Master Data
# ============================================================

class PayrollStructureForm(forms.ModelForm):
    class Meta:
        model = m.PayrollStructure
        fields = ["company", "name", "code", "use_worked_day_lines"]
        widgets = {
            "company": forms.Select(attrs={"class": "select select-bordered w-full"}),
            "name": forms.TextInput(attrs={
                "class": "input input-bordered w-full",
                "placeholder": "e.g. Staff Salary"
            }),
            "code": forms.TextInput(attrs={
                "class": "input input-bordered w-full font-mono",
                "placeholder": "STAFF"
            }),
            "use_worked_day_lines": forms.CheckboxInput(attrs={"class": "checkbox checkbox-sm"}),
        }


class SalaryRuleCategoryForm(forms.ModelForm):
    class Meta:
        model = m.SalaryRuleCategory
        fields = ["company", "name", "code", "sequence"]
        widgets = {
            "company": forms.Select(attrs={"class": "select select-bordered w-full"}),
            "name": forms.TextInput(attrs={
                "class": "input input-bordered w-full",
                "placeholder": "Basic Salary"
            }),
            "code": forms.TextInput(attrs={
                "class": "input input-bordered w-full font-mono",
                "placeholder": "BASIC"
            }),
            "sequence": forms.NumberInput(attrs={
                "class": "input input-bordered w-full",
                "min": 1
            }),
        }


class RuleParameterForm(forms.ModelForm):
    class Meta:
        model = m.RuleParameter
        fields = ["company", "code", "value"]
        widgets = {
            "company": forms.Select(attrs={"class": "select select-bordered w-full"}),
            "code": forms.TextInput(attrs={
                "class": "input input-bordered w-full font-mono",
                "placeholder": "TAX_RATE"
            }),
            "value": forms.NumberInput(attrs={
                "class": "input input-bordered w-full",
                "step": "0.0001"
            }),
        }


class SalaryRuleForm(forms.ModelForm):
    class Meta:
        model = m.SalaryRule
        fields = [
            "struct",
            "code",
            "name",
            "sequence",
            "category",
            "condition_select",
            "condition_python",
            "amount_python",
            "input_usage_employee",
            "unique_code_per_struct",
        ]
        widgets = {
            "struct": forms.Select(attrs={"class": "select select-bordered w-full"}),
            "code": forms.TextInput(attrs={
                "class": "input input-bordered w-full font-mono",
                "placeholder": "ALW_TRAN"
            }),
            "name": forms.TextInput(attrs={
                "class": "input input-bordered w-full",
                "placeholder": "Transport Allowance"
            }),
            "sequence": forms.NumberInput(attrs={"class": "input input-bordered w-full"}),
            "category": forms.Select(attrs={"class": "select select-bordered w-full"}),
            "condition_select": forms.Select(attrs={"class": "select select-bordered w-full"}),
            "condition_python": forms.Textarea(attrs={
                "class": "textarea textarea-bordered w-full font-mono",
                "rows": 3
            }),
            "amount_python": forms.Textarea(attrs={
                "class": "textarea textarea-bordered w-full font-mono",
                "rows": 6
            }),
            "input_usage_employee": forms.CheckboxInput(attrs={"class": "checkbox checkbox-sm"}),
            "unique_code_per_struct": forms.CheckboxInput(attrs={"class": "checkbox checkbox-sm"}),
        }


class InputTypeForm(forms.ModelForm):
    class Meta:
        model = m.InputType
        fields = ["company", "name", "code", "active", "is_quantity"]
        widgets = {
            "company": forms.Select(attrs={"class": "select select-bordered w-full"}),
            "name": forms.TextInput(attrs={
                "class": "input input-bordered w-full",
                "placeholder": "Transport Allowance"
            }),
            "code": forms.TextInput(attrs={
                "class": "input input-bordered w-full font-mono",
                "placeholder": "ALW_TRAN"
            }),
            "active": forms.CheckboxInput(attrs={"class": "checkbox checkbox-sm"}),
            "is_quantity": forms.CheckboxInput(attrs={"class": "checkbox checkbox-sm"}),
        }


# ============================================================
# Periods / Transactions
# ============================================================

class PayrollPeriodForm(forms.ModelForm):
    class Meta:
        model = m.PayrollPeriod
        fields = ["company", "date_from", "date_to", "month", "year", "state"]
        widgets = {
            "company": forms.Select(attrs={"class": "select select-bordered w-full"}),
            "date_from": forms.DateInput(attrs={
                "type": "date",
                "class": "input input-bordered w-full"
            }),
            "date_to": forms.DateInput(attrs={
                "type": "date",
                "class": "input input-bordered w-full"
            }),
            "month": forms.NumberInput(attrs={"class": "input input-bordered w-full"}),
            "year": forms.NumberInput(attrs={"class": "input input-bordered w-full"}),
            "state": forms.Select(attrs={"class": "select select-bordered w-full"}),
        }


class PayslipForm(forms.ModelForm):
    class Meta:
        model = m.Payslip
        fields = [
            "company",
            "employee",
            "period",
            "department",
            "job",
            "struct",
            "note",
            "state",
        ]
        widgets = {
            "company": forms.Select(attrs={"class": "select select-bordered w-full"}),
            "employee": forms.Select(attrs={"class": "select select-bordered w-full"}),
            "period": forms.Select(attrs={"class": "select select-bordered w-full"}),
            "department": forms.Select(attrs={"class": "select select-bordered w-full"}),
            "job": forms.Select(attrs={"class": "select select-bordered w-full"}),
            "struct": forms.Select(attrs={"class": "select select-bordered w-full"}),
            "note": forms.TextInput(attrs={
                "class": "input input-bordered w-full",
                "placeholder": "Optional note"
            }),
            "state": forms.Select(attrs={"class": "select select-bordered w-full"}),
        }


class PayslipInputForm(forms.ModelForm):
    class Meta:
        model = m.PayslipInput
        fields = ["company", "payslip", "input_type", "name", "sequence", "amount"]
        widgets = {
            "company": forms.Select(attrs={"class": "select select-bordered w-full"}),
            "payslip": forms.Select(attrs={"class": "select select-bordered w-full"}),
            "input_type": forms.Select(attrs={"class": "select select-bordered w-full"}),
            "name": forms.TextInput(attrs={
                "class": "input input-bordered w-full",
                "placeholder": "Optional description"
            }),
            "sequence": forms.NumberInput(attrs={"class": "input input-bordered w-full"}),
            "amount": forms.NumberInput(attrs={
                "class": "input input-bordered w-full",
                "step": "0.01"
            }),
        }


class EmployeeSalaryForm(forms.ModelForm):
    class Meta:
        model = m.EmployeeSalary
        fields = ["company", "employee", "amount", "date_start", "date_end", "note"]
        widgets = {
            "company": forms.Select(attrs={"class": "select select-bordered w-full"}),
            "employee": forms.Select(attrs={"class": "select select-bordered w-full"}),
            "amount": forms.NumberInput(attrs={
                "class": "input input-bordered w-full",
                "step": "0.01"
            }),
            "date_start": forms.DateInput(attrs={
                "type": "date",
                "class": "input input-bordered w-full"
            }),
            "date_end": forms.DateInput(attrs={
                "type": "date",
                "class": "input input-bordered w-full"
            }),
            "note": forms.TextInput(attrs={
                "class": "input input-bordered w-full",
                "placeholder": "Optional note"
            }),
        }
