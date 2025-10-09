from django import forms
from django.core.exceptions import ValidationError
from ..models import Employee
from .base import TailwindModelForm


class EmployeeForm(TailwindModelForm):
    """
    نموذج إنشاء/تعديل موظف.
    متوافق مع الحقول الجديدة (address_home, marital_status, gender, إلخ)
    ويتحقق من تطابق الشركة مع القسم/الوظيفة/المدير/الموقع.
    """
    class Meta:
        model = Employee
        fields = [
            "active", "company", "name", "user",
            "department", "job", "manager", "coach",
            "work_contact", "work_email", "work_phone", "mobile_phone",
            "work_location", "categories",
            "address_home", "private_email", "private_phone",
            "marital_status", "gender", "children",
            "identification_id", "passport_id",
            "bank_account", "car",
            "birthday", "place_of_birth",
            "emergency_contact", "emergency_phone",
            "certificate", "study_field", "study_school",
            "barcode", "pin",
        ]
        widgets = {
            "categories": forms.SelectMultiple(attrs={"class": "select select-bordered w-full", "size": 6}),
            "marital_status": forms.Select(attrs={"class": "select select-bordered w-full"}),
            "gender": forms.Select(attrs={"class": "select select-bordered w-full"}),
            "birthday": forms.DateInput(attrs={"type": "date", "class": "input input-bordered w-full"}),
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

        # ملء الشركة من القسم إن لم يتم تحديدها
        if department and not company:
            cleaned["company"] = department.company
            company = cleaned["company"]

        if not company:
            return cleaned

        # تحقق من التوافق بين الكيانات والشركة
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
