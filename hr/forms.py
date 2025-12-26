# hr/forms.py
from django import forms
from .models import Department, Job, Employee


# ============================================================
# DepartmentForm (FINAL)
# ============================================================
class DepartmentForm(forms.ModelForm):
    """
    Department form (Odoo-like, FINAL).

    Goals:
    - Allow create/update without exposing company field
    - Filter parent & manager by company
    - Prevent silent invalid forms (e.g., missing color in POST)
    """

    class Meta:
        model = Department
        fields = (
            "active",
            "name",
            "parent",
            "manager",
            "note",
            "color",
        )
        widgets = {
            "note": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # -------------------------------
        # Styling (same UX pattern)
        # -------------------------------
        base_input = {"class": "input input-bordered w-full"}
        base_select = {"class": "select select-bordered w-full"}
        base_textarea = {"class": "textarea textarea-bordered w-full"}

        if "name" in self.fields:
            self.fields["name"].widget.attrs.update(base_input)

        if "parent" in self.fields:
            self.fields["parent"].widget.attrs.update(base_select)

        if "manager" in self.fields:
            self.fields["manager"].widget.attrs.update(base_select)

        if "note" in self.fields:
            self.fields["note"].widget.attrs.update(base_textarea)

        if "active" in self.fields:
            self.fields["active"].widget.attrs.update({"class": "toggle toggle-primary"})

        # -------------------------------
        # CRITICAL: color must not break POST
        # If you don't render it, it still must validate.
        # -------------------------------
        if "color" in self.fields:
            self.fields["color"].required = False
            self.fields["color"].initial = self.instance.color if self.instance.pk else 0
            # keep it hidden (you can change to NumberInput if you want it visible)
            self.fields["color"].widget = forms.HiddenInput()

        # -------------------------------
        # Determine company (Update OR Create)
        # -------------------------------
        company = (
            getattr(self.instance, "company", None)
            or self.initial.get("company")
        )

        # -------------------------------
        # Parent department (same company, exclude self)
        # -------------------------------
        parent_qs = Department.objects.all()
        if company:
            parent_qs = parent_qs.filter(company=company)
        if self.instance.pk:
            parent_qs = parent_qs.exclude(pk=self.instance.pk)
        self.fields["parent"].queryset = parent_qs.order_by("complete_name")

        # -------------------------------
        # Manager (Employee from same company)
        # -------------------------------
        if "manager" in self.fields:
            mgr_qs = self.fields["manager"].queryset
            if company:
                mgr_qs = mgr_qs.filter(company=company, active=True)
            self.fields["manager"].queryset = mgr_qs.order_by("name")


# ============================================================
# JobForm
# ============================================================
class JobForm(forms.ModelForm):
    class Meta:
        model = Job
        fields = (
            "active",
            "company",
            "name",
            "department",
            "description",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        company = (
            self.initial.get("company")
            or getattr(self.instance, "company", None)
        )

        if company and "department" in self.fields:
            self.fields["department"].queryset = (
                self.fields["department"].queryset
                .filter(company=company)
                .order_by("complete_name")
            )


# ============================================================
# EmployeeForm
# ============================================================
class EmployeeForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = (
            "active",
            "company",
            "name",
            "user",
            "department",
            "job",
            "manager",
            "coach",
            "work_location",
            "categories",
            "barcode",
            "pin",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        company = (
            self.initial.get("company")
            or getattr(self.instance, "company", None)
        )
        if not company:
            return

        if "department" in self.fields:
            self.fields["department"].queryset = (
                self.fields["department"].queryset
                .filter(company=company, active=True)
                .order_by("complete_name")
            )

        if "job" in self.fields:
            self.fields["job"].queryset = (
                self.fields["job"].queryset
                .filter(company=company, active=True)
                .order_by("name")
            )

        for fname in ("manager", "coach"):
            if fname in self.fields:
                qs = self.fields[fname].queryset.filter(company=company, active=True)
                if self.instance.pk:
                    qs = qs.exclude(pk=self.instance.pk)
                self.fields[fname].queryset = qs.order_by("name")

        if "user" in self.fields:
            user_qs = self.fields["user"].queryset
            user_qs = user_qs.filter(company=company) | user_qs.filter(companies=company)
            self.fields["user"].queryset = user_qs.distinct().order_by("email")
