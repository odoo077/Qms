# skills/forms.py

from __future__ import annotations

from django import forms
from django.core.exceptions import ValidationError

from .models import (
    SkillType,
    SkillLevel,
    Skill,
    EmployeeSkill,
    ResumeLine,
    ResumeLineType, CompanySkill, JobSkill,
)


# ============================================================
# Base helpers
# ============================================================

class BaseCleanModelForm(forms.ModelForm):
    """
    Base form:
    - مكان موحد لإضافات مستقبلية
    """
    pass


# ============================================================
# SkillType Form (Enterprise-ready)
# ============================================================

class SkillTypeForm(BaseCleanModelForm):
    """
    Configuration form for Skill Types (Odoo-like).

    Principles:
    - No business logic here
    - Clean UI hints only
    - Validation stays in model.clean()
    """

    class Meta:
        model = SkillType
        fields = [
            "name",
            "sequence",
            "color",
            "is_certification",
            "active",
        ]
        widgets = {
            "name": forms.TextInput(attrs={
                "class": "input input-bordered w-full",
                "placeholder": "e.g. Technical Skills, Soft Skills",
            }),
            "sequence": forms.NumberInput(attrs={
                "class": "input input-bordered w-full",
                "min": 1,
            }),
            "color": forms.NumberInput(attrs={
                "class": "input input-bordered w-full",
                "min": 0,
                "max": 11,
            }),
            "is_certification": forms.CheckboxInput(attrs={
                "class": "checkbox",
            }),
            "active": forms.CheckboxInput(attrs={
                "class": "checkbox",
            }),
        }
        help_texts = {
            "sequence": "Lower sequence appears first in lists.",
            "color": "UI color index (0–11) used for badges and charts.",
            "is_certification": "Mark this type as certification-based (e.g. PMP, ITIL).",
            "active": "Inactive types will be hidden from selection lists.",
        }


# ============================================================
# SkillLevel
# ============================================================

class SkillLevelForm(BaseCleanModelForm):
    """
    Production-ready form for SkillLevel.
    """

    class Meta:
        model = SkillLevel
        fields = [
            "skill_type",
            "name",
            "level_progress",
            "default_level",
            "active",
        ]

        widgets = {
            "skill_type": forms.Select(attrs={"class": "select select-bordered w-full"}),
            "name": forms.TextInput(attrs={"class": "input input-bordered w-full"}),
            "level_progress": forms.NumberInput(
                attrs={
                    "class": "input input-bordered w-full",
                    "min": 0,
                    "max": 100,
                }
            ),
        }

    def clean_level_progress(self):
        value = self.cleaned_data.get("level_progress")
        if value is None:
            return value
        if not 0 <= value <= 100:
            raise ValidationError("Progress must be between 0 and 100.")
        return value

    def clean(self):
        """
        Extra safety to avoid UI misuse (DB constraints already exist).
        """
        cleaned = super().clean()
        skill_type = cleaned.get("skill_type")
        default_level = cleaned.get("default_level")

        if skill_type and default_level:
            qs = SkillLevel.objects.filter(
                skill_type=skill_type,
                default_level=True,
            )
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)

            if qs.exists():
                self.add_error(
                    "default_level",
                    "There is already a default level for this skill type.",
                )

        return cleaned



# ============================================================
# Skill
# ============================================================

class SkillForm(BaseCleanModelForm):
    """
    Skill form – production ready.

    - Explicit fields
    - Clean defaults
    - Relies on DB constraints for uniqueness
    """

    class Meta:
        model = Skill
        fields = [
            "skill_type",
            "name",
            "sequence",
            "active",
        ]

        widgets = {
            "skill_type": forms.Select(attrs={
                "class": "select select-bordered w-full",
            }),
            "name": forms.TextInput(attrs={
                "class": "input input-bordered w-full",
                "placeholder": "e.g. Python, Odoo Development, Communication",
            }),
            "sequence": forms.NumberInput(attrs={
                "class": "input input-bordered w-full",
                "min": 0,
            }),
            "active": forms.CheckboxInput(attrs={
                "class": "checkbox checkbox-primary",
            }),
        }

    def clean_name(self):
        name = (self.cleaned_data.get("name") or "").strip()
        if not name:
            raise ValidationError("Skill name is required.")
        return name



# ============================================================
# EmployeeSkill
# ============================================================

class EmployeeSkillForm(BaseCleanModelForm):
    """
    Employee Skill form with strict consistency rules:
    - Skill must belong to Skill Type
    - Level must belong to Skill Type
    - Skill / Level dropdowns filtered by Skill Type
    """

    class Meta:
        model = EmployeeSkill
        fields = [
            "employee",
            "skill_type",
            "skill",
            "skill_level",
            "valid_from",
            "valid_to",
            "note",
            "active",
        ]
        widgets = {
            "valid_from": forms.DateInput(
                attrs={"type": "date", "class": "input input-bordered w-full"}
            ),
            "valid_to": forms.DateInput(
                attrs={"type": "date", "class": "input input-bordered w-full"}
            ),
            "note": forms.Textarea(
                attrs={"rows": 3, "class": "textarea textarea-bordered w-full"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # ----------------------------------
        # Resolve selected skill_type
        # ----------------------------------
        skill_type_id = (
            self.data.get("skill_type")
            or getattr(self.instance, "skill_type_id", None)
        )

        # ----------------------------------
        # Filter Skill by SkillType
        # ----------------------------------
        if skill_type_id:
            self.fields["skill"].queryset = (
                Skill.objects.filter(skill_type_id=skill_type_id, active=True)
                .order_by("sequence", "name")
            )
            self.fields["skill_level"].queryset = (
                SkillLevel.objects.filter(skill_type_id=skill_type_id, active=True)
                .order_by("level_progress", "name")
            )
        else:
            self.fields["skill"].queryset = Skill.objects.none()
            self.fields["skill_level"].queryset = SkillLevel.objects.none()

    def clean(self):
        cleaned = super().clean()

        skill_type = cleaned.get("skill_type")
        skill = cleaned.get("skill")
        level = cleaned.get("skill_level")

        # ----------------------------------
        # Cross consistency validation
        # ----------------------------------
        if skill and skill_type and skill.skill_type_id != skill_type.id:
            self.add_error(
                "skill",
                "Selected skill does not belong to the selected skill type."
            )

        if level and skill_type and level.skill_type_id != skill_type.id:
            self.add_error(
                "skill_level",
                "Selected level does not belong to the selected skill type."
            )

        return cleaned


# ============================================================
# ResumeLineType
# ============================================================

class ResumeLineTypeForm(BaseCleanModelForm):

    class Meta:
        model = ResumeLineType
        fields = [
            "name",
            "sequence",
            "active",
            "properties_definition",
        ]


# ============================================================
# ResumeLine
# ============================================================

class ResumeLineForm(BaseCleanModelForm):

    class Meta:
        model = ResumeLine
        fields = [
            "employee",
            "line_type",
            "name",
            "description",
            "date_start",
            "date_end",
            "certificate_file",
            "external_url",
            "active",
        ]

        # ✅ الحل هنا — نفس Best Practice
        widgets = {
            "date_start": forms.DateInput(
                attrs={
                    "type": "date",
                    "class": "input input-bordered w-full",
                }
            ),
            "date_end": forms.DateInput(
                attrs={
                    "type": "date",
                    "class": "input input-bordered w-full",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()

        start = cleaned.get("date_start")
        end = cleaned.get("date_end")

        if start and end and end < start:
            self.add_error(
                "date_end",
                "End date must be after or equal to start date."
            )

        return cleaned


# ============================================================
# CompanySkillForm
# ============================================================
class CompanySkillForm(forms.ModelForm):
    class Meta:
        model = CompanySkill
        fields = ("company", "skill", "active")
        widgets = {
            "company": forms.Select(attrs={"class": "select select-bordered w-full"}),
            "skill": forms.Select(attrs={"class": "select select-bordered w-full"}),
            "active": forms.CheckboxInput(attrs={"class": "checkbox"}),
        }


# ============================================================
# JobSkillForm (Skill Matrix)
# ============================================================
class JobSkillForm(forms.ModelForm):
    class Meta:
        model = JobSkill
        fields = ("job", "skill", "min_level", "active")
        widgets = {
            "job": forms.Select(attrs={"class": "select select-bordered w-full"}),
            "skill": forms.Select(attrs={"class": "select select-bordered w-full"}),
            "min_level": forms.Select(attrs={"class": "select select-bordered w-full"}),
            "active": forms.CheckboxInput(attrs={"class": "checkbox"}),
        }
