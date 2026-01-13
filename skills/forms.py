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
# SkillType
# ============================================================

class SkillTypeForm(BaseCleanModelForm):

    class Meta:
        model = SkillType
        fields = [
            "name",
            "sequence",
            "color",
            "is_certification",
            "active",
        ]


# ============================================================
# SkillLevel
# ============================================================

class SkillLevelForm(BaseCleanModelForm):

    class Meta:
        model = SkillLevel
        fields = [
            "skill_type",
            "name",
            "level_progress",
            "default_level",
            "active",
        ]

    def clean_level_progress(self):
        value = self.cleaned_data.get("level_progress")
        if value is None:
            return value
        if not 0 <= value <= 100:
            raise ValidationError("Progress must be between 0 and 100.")
        return value


# ============================================================
# Skill
# ============================================================

class SkillForm(BaseCleanModelForm):

    class Meta:
        model = Skill
        fields = [
            "skill_type",
            "name",
            "sequence",
            "active",
        ]


# ============================================================
# EmployeeSkill
# ============================================================

class EmployeeSkillForm(BaseCleanModelForm):

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
                attrs={
                    "type": "date",
                    "class": "input input-bordered w-full",
                }
            ),
            "valid_to": forms.DateInput(
                attrs={
                    "type": "date",
                    "class": "input input-bordered w-full",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        skill_type_id = (
            self.data.get("skill_type")
            or getattr(self.instance, "skill_type_id", None)
        )

        if skill_type_id:
            self.fields["skill"].queryset = (
                self.fields["skill"]
                .queryset
                .filter(skill_type_id=skill_type_id)
                .order_by("sequence", "name")
            )
        else:
            self.fields["skill"].queryset = self.fields["skill"].queryset.none()

        if skill_type_id:
            self.fields["skill_level"].queryset = (
                self.fields["skill_level"]
                .queryset
                .filter(skill_type_id=skill_type_id)
                .order_by("level_progress", "name")
            )
        else:
            self.fields["skill_level"].queryset = self.fields["skill_level"].queryset.none()

    def clean(self):
        cleaned = super().clean()

        skill_type = cleaned.get("skill_type")
        skill = cleaned.get("skill")
        level = cleaned.get("skill_level")

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
