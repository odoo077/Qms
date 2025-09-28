from django import forms
from skills.models import HrEmployeeSkill

class EmployeeSkillForm(forms.ModelForm):
    class Meta:
        model = HrEmployeeSkill
        fields = ["employee", "skill_type", "skill", "skill_level", "valid_from", "valid_to"]
