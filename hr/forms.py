# hr/forms.py
from django import forms
from django.core.exceptions import ValidationError

from base.models import Company
from .models import Department, Job, Employee, EmployeeEducation, CareerPolicy, JobCareerPath


# ============================================================
# DepartmentForm (FINAL - company selectable + auto-filled)
# ============================================================
class DepartmentForm(forms.ModelForm):
    """
    - Company field is visible
    - Auto-filled with active company (or first allowed)
    - On Create: user can change company if multiple allowed
    - On Update: company is locked to the object company
    - Parent/Manager filtered by selected company
    """

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        self.allowed_company_ids = kwargs.pop("allowed_company_ids", None)
        self.active_company_id = kwargs.pop("active_company_id", None)
        super().__init__(*args, **kwargs)

        # --------------------------------
        # Styling (Tailwind + DaisyUI)
        # --------------------------------
        base_input = {"class": "input input-bordered w-full"}
        base_select = {"class": "select select-bordered w-full"}
        base_textarea = {"class": "textarea textarea-bordered w-full"}

        if "name" in self.fields:
            self.fields["name"].widget.attrs.update(base_input)

        if "company" in self.fields:
            self.fields["company"].widget.attrs.update(base_select)

        if "parent" in self.fields:
            self.fields["parent"].widget.attrs.update(base_select)

        if "manager" in self.fields:
            self.fields["manager"].widget.attrs.update(base_select)

        if "note" in self.fields:
            self.fields["note"].widget.attrs.update(base_textarea)

        if "active" in self.fields:
            self.fields["active"].widget.attrs.update({"class": "toggle toggle-primary"})

        # --------------------------------
        # Make color safe (even if not rendered)
        # --------------------------------
        if "color" in self.fields:
            self.fields["color"].required = False
            if not self.instance.pk and self.fields["color"].initial in (None, ""):
                self.fields["color"].initial = 0

        # --------------------------------
        # Company queryset (allowed only)
        # --------------------------------
        company_qs = Company.objects.all()
        if self.allowed_company_ids:
            company_qs = company_qs.filter(id__in=self.allowed_company_ids)
        self.fields["company"].queryset = company_qs.order_by("name")

        # --------------------------------
        # Determine selected company (POST > instance > initial > active > first allowed)
        # --------------------------------
        selected_company_id = None

        if self.is_bound:
            selected_company_id = (self.data.get(self.add_prefix("company")) or "").strip() or None
            if selected_company_id:
                try:
                    selected_company_id = int(selected_company_id)
                except ValueError:
                    selected_company_id = None
        if not selected_company_id and getattr(self.instance, "company_id", None):
            selected_company_id = self.instance.company_id
        if not selected_company_id and self.initial.get("company"):
            try:
                selected_company_id = int(self.initial.get("company"))
            except Exception:
                selected_company_id = getattr(self.initial.get("company"), "id", None)
        if not selected_company_id and self.active_company_id:
            selected_company_id = self.active_company_id
        if not selected_company_id and self.allowed_company_ids:
            selected_company_id = self.allowed_company_ids[0] if len(self.allowed_company_ids) else None

        # set initial (for first render)
        if selected_company_id and not self.is_bound and not self.instance.pk:
            self.fields["company"].initial = selected_company_id

        # lock company on update
        if self.instance.pk:
            self.fields["company"].disabled = True

        # ensure instance.company is set early so model.clean() sees it during is_valid()
        if selected_company_id and not self.instance.company_id:
            self.instance.company_id = selected_company_id

        # --------------------------------
        # Filter Parent by selected company
        # --------------------------------
        parent_qs = Department.objects.all()
        if selected_company_id:
            parent_qs = parent_qs.filter(company_id=selected_company_id)

        if self.instance.pk:
            parent_qs = parent_qs.exclude(pk=self.instance.pk)

        self.fields["parent"].queryset = parent_qs.order_by("complete_name")

        # --------------------------------
        # Filter Manager by selected company
        # --------------------------------
        if "manager" in self.fields:
            mgr_qs = self.fields["manager"].queryset
            if selected_company_id:
                mgr_qs = mgr_qs.filter(company_id=selected_company_id, active=True)
            self.fields["manager"].queryset = mgr_qs.order_by("name")

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
        widgets = {
            "note": forms.Textarea(attrs={"rows": 4}),
        }

    def clean_company(self):
        company = self.cleaned_data.get("company")
        if self.instance.pk:
            return self.instance.company
        if self.allowed_company_ids and company and company.id not in self.allowed_company_ids:
            raise ValidationError("Company is outside active scope.")
        return company


# ============================================================
# JobForm (FINAL)
# ============================================================
class JobForm(forms.ModelForm):
    accepts_allowed_company_ids = True
    """
    Job form (Odoo-like, FINAL):
    - Company field visible
    - Defaults to first allowed company
    - Department select cascades by company (HTMX)
    - Enforces department-company consistency in clean()
    """

    class Meta:
        model = Job
        fields = (
            "active",
            "company",
            "name",
            "department",
            "description",
            "requirements",
            "sequence",
            "recruiter",
            "contract_type",
            "no_of_recruitment",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "requirements": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        self.allowed_company_ids = kwargs.pop("allowed_company_ids", None)
        super().__init__(*args, **kwargs)

        # -------------------------------
        # Styling (same UX pattern)
        # -------------------------------
        base_input = {"class": "input input-bordered w-full"}
        base_select = {"class": "select select-bordered w-full"}
        base_textarea = {"class": "textarea textarea-bordered w-full"}

        for f in ("name", "sequence", "no_of_recruitment"):
            if f in self.fields:
                self.fields[f].widget.attrs.update(base_input)

        for f in ("company", "department", "recruiter", "contract_type"):
            if f in self.fields:
                self.fields[f].widget.attrs.update(base_select)

        for f in ("description", "requirements"):
            if f in self.fields:
                self.fields[f].widget.attrs.update(base_textarea)

        if "active" in self.fields:
            self.fields["active"].widget.attrs.update({"class": "toggle toggle-primary"})

        # -------------------------------
        # Limit company choices to allowed companies
        # -------------------------------
        if self.allowed_company_ids is not None and "company" in self.fields:
            self.fields["company"].queryset = self.fields["company"].queryset.filter(id__in=self.allowed_company_ids)

        # -------------------------------
        # Default company (create)
        # -------------------------------
        if not self.instance.pk and "company" in self.fields:
            if self.initial.get("company") is None and self.allowed_company_ids:
                self.initial["company"] = self.allowed_company_ids[0]

        # -------------------------------
        # Determine current company (update OR create)
        # -------------------------------
        company = getattr(self.instance, "company", None) or self.initial.get("company")

        # -------------------------------
        # Department queryset (filtered by company)
        # -------------------------------
        if "department" in self.fields:
            dept_qs = Department.objects.filter(active=True)
            if company:
                dept_qs = dept_qs.filter(company=company)
            self.fields["department"].queryset = dept_qs.order_by("complete_name")

            # HTMX: when company changes, reload options
            if "company" in self.fields:
                self.fields["company"].widget.attrs.update({
                    "hx-get": "/hr/ajax/departments/options/",
                    "hx-target": "#id_department",
                    "hx-swap": "innerHTML",
                    "hx-include": "#id_company",
                })
                self.fields["department"].widget.attrs.update({
                    "id": "id_department",
                })

    def clean(self):
        cleaned = super().clean()
        company = cleaned.get("company")
        department = cleaned.get("department")

        if department and company and department.company_id != company.id:
            self.add_error("department", "Department must belong to the selected company.")
        return cleaned


# ============================================================
# EmployeeForm
# ============================================================
class EmployeeForm(forms.ModelForm):
    """
    Employee form (Odoo-like):
    - Company visible
    - Company scoped to allowed companies
    - On create: default = active company (or first allowed)
    - On update: company locked (safe best practice)
    - Department/Job/Manager/Coach/User filtered by selected company
    - Styling consistent (Tailwind + DaisyUI)
    """

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        self.allowed_company_ids = kwargs.pop("allowed_company_ids", None)
        self.active_company_id = kwargs.pop("active_company_id", None)
        super().__init__(*args, **kwargs)

        # -------------------------------
        # Styling (Tailwind + DaisyUI)
        # -------------------------------
        base_input = {"class": "input input-bordered w-full"}
        base_select = {"class": "select select-bordered w-full"}
        base_toggle = {"class": "toggle toggle-primary"}

        for f in ("name", "barcode", "pin"):
            if f in self.fields:
                self.fields[f].widget.attrs.update(base_input)

        for f in ("company", "user", "department", "job", "manager", "coach", "work_location", "categories"):
            if f in self.fields:
                self.fields[f].widget.attrs.update(base_select)

        if "active" in self.fields:
            self.fields["active"].widget.attrs.update(base_toggle)

        # -------------------------------
        # Company queryset (allowed only)
        # -------------------------------
        if "company" in self.fields:
            company_qs = Company.objects.all()
            if self.allowed_company_ids:
                company_qs = company_qs.filter(id__in=self.allowed_company_ids)
            self.fields["company"].queryset = company_qs.order_by("name")

        # -------------------------------
        # Determine selected company (POST > instance > initial > active > first allowed)
        # -------------------------------
        selected_company_id = None

        if self.is_bound:
            raw = (self.data.get(self.add_prefix("company")) or "").strip() or None
            if raw:
                try:
                    selected_company_id = int(raw)
                except ValueError:
                    selected_company_id = None

        if not selected_company_id and getattr(self.instance, "company_id", None):
            selected_company_id = self.instance.company_id

        if not selected_company_id and self.initial.get("company"):
            try:
                selected_company_id = int(self.initial.get("company"))
            except Exception:
                selected_company_id = getattr(self.initial.get("company"), "id", None)

        if not selected_company_id and self.active_company_id:
            selected_company_id = self.active_company_id

        if not selected_company_id and self.allowed_company_ids:
            selected_company_id = self.allowed_company_ids[0] if len(self.allowed_company_ids) else None

        # default initial company on create
        if selected_company_id and not self.is_bound and not self.instance.pk and "company" in self.fields:
            self.fields["company"].initial = selected_company_id

        # lock company on update (safe)
        if self.instance.pk and "company" in self.fields:
            self.fields["company"].disabled = True

        # ensure instance.company early for model.clean/full_clean
        if selected_company_id and not self.instance.company_id:
            self.instance.company_id = selected_company_id

        # if no company → stop filtering
        if not selected_company_id:
            return

        # -------------------------------
        # Department (same company + active)
        # -------------------------------
        if "department" in self.fields:
            self.fields["department"].queryset = (
                Department.objects
                .filter(company_id=selected_company_id, active=True)
                .order_by("complete_name")
            )

        # -------------------------------
        # Job (same company + active)
        # -------------------------------
        if "job" in self.fields:
            self.fields["job"].queryset = (
                Job.objects
                .filter(company_id=selected_company_id, active=True)
                .order_by("name")
            )

        # -------------------------------
        # Manager/Coach (same company + active, exclude self)
        # -------------------------------
        for fname in ("manager", "coach"):
            if fname in self.fields:
                qs = Employee.objects.filter(company_id=selected_company_id, active=True)
                if self.instance.pk:
                    qs = qs.exclude(pk=self.instance.pk)
                self.fields[fname].queryset = qs.order_by("name")

        # -------------------------------
        # User (allowed in company context)
        # -------------------------------
        if "user" in self.fields:
            user_qs = self.fields["user"].queryset
            user_qs = user_qs.filter(company_id=selected_company_id) | user_qs.filter(companies__id=selected_company_id)
            self.fields["user"].queryset = user_qs.distinct().order_by("email")

        self.fields.pop("current_status", None)

    class Meta:
        model = Employee
        fields = (
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

    def clean_company(self):
        company = self.cleaned_data.get("company")
        if self.instance.pk:
            # company locked
            return self.instance.company
        if self.allowed_company_ids and company and company.id not in self.allowed_company_ids:
            raise ValidationError("Company is outside active scope.")
        return company

    def clean(self):
        cleaned = super().clean()
        company = cleaned.get("company") or getattr(self.instance, "company", None)

        # enforce cross-company consistency explicitly (user friendly)
        dept = cleaned.get("department")
        job = cleaned.get("job")
        manager = cleaned.get("manager")
        coach = cleaned.get("coach")

        if company:
            if dept and dept.company_id != company.id:
                self.add_error("department", "Department must belong to the selected company.")
            if job and job.company_id != company.id:
                self.add_error("job", "Job must belong to the selected company.")
            if manager and manager.company_id != company.id:
                self.add_error("manager", "Manager must belong to the selected company.")
            if coach and coach.company_id != company.id:
                self.add_error("coach", "Coach must belong to the selected company.")

        return cleaned


# ============================================================
# EmployeeEducationForm
# ============================================================
class EmployeeEducationForm(forms.ModelForm):
    """
    Employee Education Form (Modal – Odoo-like)
    """

    class Meta:
        model = EmployeeEducation
        fields = (
            "certificate",
            "field_of_study",
            "institution",
            "start_year",
            "end_year",
            "notes",
        )
        widgets = {
            "certificate": forms.TextInput(attrs={"class": "input input-bordered w-full"}),
            "field_of_study": forms.TextInput(attrs={"class": "input input-bordered w-full"}),
            "institution": forms.TextInput(attrs={"class": "input input-bordered w-full"}),
            "start_year": forms.NumberInput(attrs={"class": "input input-bordered w-full"}),
            "end_year": forms.NumberInput(attrs={"class": "input input-bordered w-full"}),
            "notes": forms.Textarea(attrs={"class": "textarea textarea-bordered w-full", "rows": 3}),
        }


# ============================================================
# CareerPolicyForm (FINAL – Company Scoped, NO ACL)
# ============================================================

class CareerPolicyForm(forms.ModelForm):
    """
    Career Policy Form (Enterprise-grade):
    - Company scoped (allowed_company_ids)
    - No record-level ACL
    - No Django permissions logic
    """

    class Meta:
        model = CareerPolicy
        fields = (
            "name",
            "company",
            "min_ready_score",
            "min_near_ready_score",
            "gap_weight",
            "ok_weight",
            "missing_weight",
            "active",
        )
        widgets = {
            "name": forms.TextInput(attrs={"class": "input input-bordered w-full"}),
            "company": forms.Select(attrs={"class": "select select-bordered w-full"}),
            "min_ready_score": forms.NumberInput(attrs={"class": "input input-bordered w-full"}),
            "min_near_ready_score": forms.NumberInput(attrs={"class": "input input-bordered w-full"}),
            "gap_weight": forms.NumberInput(attrs={
                "class": "input input-bordered w-full",
                "step": "0.1",
            }),
            "ok_weight": forms.NumberInput(attrs={
                "class": "input input-bordered w-full",
                "step": "0.1",
            }),
            "missing_weight": forms.NumberInput(attrs={
                "class": "input input-bordered w-full",
                "step": "0.1",
            }),
            "active": forms.CheckboxInput(attrs={"class": "toggle toggle-primary"}),
        }

    def __init__(self, *args, **kwargs):
        # --------------------------------------------------
        # Accept company scope from BaseScoped views
        # --------------------------------------------------
        self.allowed_company_ids = kwargs.pop("allowed_company_ids", None)
        super().__init__(*args, **kwargs)

        # --------------------------------------------------
        # Limit company choices (Company Scope)
        # --------------------------------------------------
        if self.allowed_company_ids is not None and "company" in self.fields:
            self.fields["company"].queryset = (
                self.fields["company"]
                .queryset
                .filter(id__in=self.allowed_company_ids)
                .order_by("name")
            )

        # --------------------------------------------------
        # Default company on CREATE
        # --------------------------------------------------
        if not self.instance.pk and self.allowed_company_ids:
            self.initial.setdefault("company", self.allowed_company_ids[0])

    def clean(self):
        cleaned = super().clean()

        ready = cleaned.get("min_ready_score")
        near = cleaned.get("min_near_ready_score")

        # --------------------------------------------------
        # Business rule validation
        # --------------------------------------------------
        if ready is not None and near is not None and near >= ready:
            self.add_error(
                "min_near_ready_score",
                "Near Ready score must be lower than Ready score."
            )

        return cleaned


# ============================================================
# Career Path
# ============================================================
class JobCareerPathForm(forms.ModelForm):
    class Meta:
        model = JobCareerPath
        fields = (
            "from_job",
            "to_job",
            "sequence",
            "active",
        )

    def clean(self):
        cleaned = super().clean()
        from_job = cleaned.get("from_job")
        to_job = cleaned.get("to_job")

        if from_job and to_job and from_job == to_job:
            raise forms.ValidationError(
                "Source job and destination job cannot be the same."
            )

        return cleaned

