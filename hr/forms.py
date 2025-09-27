# hr/forms.py
from django import forms
from django.core.exceptions import ValidationError
from .models import Department, Job, WorkLocation, Employee, ContractType, EmployeeCategory

_TW_INPUT = "input input-bordered w-full"
_TW_SELECT = "select select-bordered w-full"
_TW_TEXTAREA = "textarea textarea-bordered w-full"

class TailwindModelForm(forms.ModelForm):
    """
    قاعدة بسيطة لإضافة كلاس Tailwind/DaisyUI تلقائيًا.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, (forms.TextInput, forms.EmailInput, forms.NumberInput, forms.PasswordInput)):
                widget.attrs.setdefault("class", _TW_INPUT)
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                widget.attrs.setdefault("class", _TW_SELECT)
            elif isinstance(widget, forms.Textarea):
                widget.attrs.setdefault("class", _TW_TEXTAREA)
            else:
                widget.attrs.setdefault("class", _TW_INPUT)


class EmployeeForm(TailwindModelForm):
    """
    نموذج موظف بأسلوب Odoo:
    - company تبقى Editable (مطابق لمنطق Odoo)
    - تحقق من تطابق شركة القسم/الوظيفة/الموقع مع شركة الموظف
    - عندما يختار قسمًا ولم يحدّد شركة، نملأ الشركة تلقائيًا من القسم
    """
    class Meta:
        model = Employee
        fields = [
            "active",
            "company",
            "name", "user",
            "department", "job", "manager", "coach",
            "work_contact", "work_email", "work_phone", "mobile_phone",
            "work_location",
            "categories",
            "barcode", "pin",
        ]
        widgets = {
            "categories": forms.SelectMultiple(attrs={"class": "select select-bordered w-full", "size": 6}),
        }

    def clean(self):
        cleaned = super().clean()
        company = cleaned.get("company")
        department = cleaned.get("department")
        job = cleaned.get("job")
        work_location = cleaned.get("work_location")
        work_contact = cleaned.get("work_contact")
        manager = cleaned.get("manager")
        coach = cleaned.get("coach")

        # لو حدّد قسمًا ولم يضع شركة، استخدم شركة القسم
        if department and not company:
            cleaned["company"] = department.company

        company = cleaned.get("company")
        if not company:
            return cleaned

        # تحقق التطابق مع الشركة
        def _check(obj, label):
            if obj and getattr(obj, "company_id", None) and obj.company_id != company.id:
                raise ValidationError({label: "Must belong to the same company as Employee."})

        _check(department, "department")
        _check(job, "job")
        _check(work_location, "work_location")
        _check(work_contact, "work_contact")
        if manager and manager.company_id != company.id:
            raise ValidationError({"manager": "Manager must belong to the same company."})
        if coach and coach.company_id != company.id:
            raise ValidationError({"coach": "Coach must belong to the same company."})

        return cleaned



class DepartmentForm(TailwindModelForm):
    class Meta:
        model = Department
        fields = ["active", "name", "company", "parent", "manager", "note", "color"]

    def clean(self):
        cleaned = super().clean()
        company = cleaned.get("company")
        parent = cleaned.get("parent")
        manager: Employee = cleaned.get("manager")

        if parent and not company:
            cleaned["company"] = parent.company
            company = cleaned["company"]

        if company:
            if parent and parent.company_id != company.id:
                raise ValidationError({"parent": "Parent must belong to the same company."})
            if manager and manager.company_id != company.id:
                raise ValidationError({"manager": "Manager must belong to the same company."})
        return cleaned


class JobForm(TailwindModelForm):
    class Meta:
        model = Job
        fields = [
            "active", "name", "sequence",
            "company", "department", "recruiter", "contract_type",
            "no_of_recruitment", "description", "requirements",
        ]

    def clean(self):
        cleaned = super().clean()
        company = cleaned.get("company")
        department = cleaned.get("department")
        if department and not company:
            cleaned["company"] = department.company
            company = cleaned["company"]
        if company and department and department.company_id != company.id:
            raise ValidationError({"department": "Department must belong to the same company."})
        return cleaned


class WorkLocationForm(TailwindModelForm):
    class Meta:
        model = WorkLocation
        fields = ["active", "name", "company", "location_type", "address", "location_number"]

    def clean(self):
        cleaned = super().clean()
        company = cleaned.get("company")
        address = cleaned.get("address")
        if company and address and getattr(address, "company_id", None) and address.company_id != company.id:
            raise ValidationError({"address": "Address must belong to the same company."})
        return cleaned


class EmployeeCategoryForm(TailwindModelForm):
    class Meta:
        model = EmployeeCategory
        fields = ["name", "color"]

class ContractTypeForm(TailwindModelForm):
    class Meta:
        model = ContractType
        fields = ["name", "code", "sequence"]