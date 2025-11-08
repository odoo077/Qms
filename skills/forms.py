# skills/forms.py
from django import forms
from .models import SkillType, SkillLevel, Skill, EmployeeSkill, ResumeLine, ResumeLineType


class SkillTypeForm(forms.ModelForm):
    class Meta:
        model = SkillType
        fields = ["name", "sequence", "color", "is_certification", "active"]


class SkillLevelForm(forms.ModelForm):
    class Meta:
        model = SkillLevel
        fields = ["skill_type", "name", "level_progress", "default_level", "active"]


class SkillForm(forms.ModelForm):
    class Meta:
        model = Skill
        fields = ["skill_type", "name", "sequence", "active"]


class EmployeeSkillForm(forms.ModelForm):
    class Meta:
        model = EmployeeSkill
        fields = ["employee", "skill_type", "skill", "skill_level", "valid_from", "valid_to", "note", "active"]


class ResumeLineTypeForm(forms.ModelForm):
    class Meta:
        model = ResumeLineType
        fields = ["name", "sequence", "active", "properties_definition"]


class ResumeLineForm(forms.ModelForm):
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
