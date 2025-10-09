from django import forms
from django.core.exceptions import ValidationError
from skills.models import HrSkillType
from .base import TailwindModelForm


class SkillTypeForm(TailwindModelForm):
    class Meta:
        model = HrSkillType
        fields = ["active", "name", "sequence", "color", "is_certification"]

    def clean_color(self):
        c = self.cleaned_data.get("color")
        # نطاق لوني اختياري (1..11 كما في Odoo عادةً)
        if c is not None and (c < 1 or c > 11):
            raise ValidationError("Color should be between 1 and 11.")
        return c
