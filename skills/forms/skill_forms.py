from django import forms
from skills.models import HrSkillType, HrSkillLevel, HrSkill

class SkillTypeForm(forms.ModelForm):
    class Meta:
        model = HrSkillType
        fields = ["name", "sequence", "color", "is_certification", "active"]

class SkillLevelForm(forms.ModelForm):
    class Meta:
        model = HrSkillLevel
        fields = ["skill_type", "name", "level_progress", "default_level"]

class SkillForm(forms.ModelForm):
    class Meta:
        model = HrSkill
        fields = ["skill_type", "name", "sequence"]
