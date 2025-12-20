# hr/forms.py
from django import forms
from .models import Department, Job, Employee


# ============================================================
# DepartmentForm
# ============================================================
class DepartmentForm(forms.ModelForm):
    """
    Department form (Odoo-like).

    Responsibilities:
    - Display editable fields only
    - Filter parent & manager by company
    - No business validation here (handled in model.clean)
    """

    class Meta:
        model = Department
        fields = (
            "active",
            "company",
            "name",
            "parent",
            "manager",
            "note",
            "color",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        company = (
            self.initial.get("company")
            or getattr(self.instance, "company", None)
        )

        # -------------------------------
        # Parent department (same company, no self)
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
    """
    Job form.

    Responsibilities:
    - Filter department by company
    """

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
                self.fields["department"]
                .queryset
                .filter(company=company)
                .order_by("complete_name")
            )


# ============================================================
# EmployeeForm
# ============================================================
class EmployeeForm(forms.ModelForm):
    """
    Employee form (Odoo-like).

    Notes:
    - This form is purely UI-level
    - All business rules live in Employee.clean()
    """

    class Meta:
        model = Employee
        fields = (
            # Core
            "active",
            "company",
            "name",
            "user",

            # Organization
            "department",
            "job",
            "manager",
            "coach",

            # Work
            "work_location",
            "categories",

            # Identifiers
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

        # -------------------------------
        # Department
        # -------------------------------
        if "department" in self.fields:
            self.fields["department"].queryset = (
                self.fields["department"]
                .queryset
                .filter(company=company, active=True)
                .order_by("complete_name")
            )

        # -------------------------------
        # Job
        # -------------------------------
        if "job" in self.fields:
            self.fields["job"].queryset = (
                self.fields["job"]
                .queryset
                .filter(company=company, active=True)
                .order_by("name")
            )

        # -------------------------------
        # Manager / Coach (Employees in same company)
        # -------------------------------
        for fname in ("manager", "coach"):
            if fname in self.fields:
                qs = self.fields[fname].queryset.filter(
                    company=company,
                    active=True,
                )
                if self.instance.pk:
                    qs = qs.exclude(pk=self.instance.pk)
                self.fields[fname].queryset = qs.order_by("name")

        # -------------------------------
        # User (allowed users for this company)
        # -------------------------------
        if "user" in self.fields:
            user_qs = self.fields["user"].queryset
            user_qs = user_qs.filter(
                company=company
            ) | user_qs.filter(
                companies=company
            )
            self.fields["user"].queryset = user_qs.distinct().order_by("email")
