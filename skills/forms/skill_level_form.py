from django import forms
from django.core.exceptions import ValidationError
from skills.models import HrSkillLevel
from .base import TailwindModelForm


class SkillLevelForm(TailwindModelForm):
    class Meta:
        model = HrSkillLevel
        fields = ["skill_type", "name", "level_progress", "default_level"]

    def clean_level_progress(self):
        p = self.cleaned_data.get("level_progress")
        if p is None or not (0 <= p <= 100):
            raise ValidationError("Level progress must be between 0 and 100.")
        return p
