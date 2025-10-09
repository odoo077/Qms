from django import forms
from skills.models import HrSkill
from .base import TailwindModelForm


class SkillForm(TailwindModelForm):
    class Meta:
        model = HrSkill
        fields = ["active", "skill_type", "name", "sequence"]
