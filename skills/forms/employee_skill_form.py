from django import forms
from django.core.exceptions import ValidationError
from skills.models import HrEmployeeSkill, HrSkill, HrSkillLevel, HrSkillType
from .base import TailwindModelForm

from skills.services.employee_skill_service import (
    add_skill,
    update_skill_versioned,
)


class EmployeeSkillForm(TailwindModelForm):
    """
    نموذج إنشاء/تعديل مهارة موظف وفق منطق Odoo (versioned writes).
    - لا يعتمد على ModelForm.save() الافتراضي في التعديلات.
    - يقوم بفلترة skill/level حسب skill_type.
    """

    class Meta:
        model = HrEmployeeSkill
        fields = ["employee", "skill_type", "skill", "skill_level", "valid_from", "valid_to"]
        widgets = {
            "valid_from": forms.DateInput(attrs={"type": "date"}),
            "valid_to": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        skill_type = None
        # استنتاج skill_type من instance أو POST
        if self.instance and self.instance.pk:
            skill_type = self.instance.skill_type
        st_id = (self.data.get("skill_type") or self.initial.get("skill_type") or (skill_type.id if skill_type else None))

        # فلترة القوائم حسب skill_type
        if st_id:
            self.fields["skill"].queryset = HrSkill.objects.filter(skill_type_id=st_id).order_by("sequence", "name")
            self.fields["skill_level"].queryset = HrSkillLevel.objects.filter(skill_type_id=st_id).order_by("level_progress", "id")
        else:
            # بدون skill_type نخليها فارغة لحين الاختيار
            self.fields["skill"].queryset = HrSkill.objects.none()
            self.fields["skill_level"].queryset = HrSkillLevel.objects.none()

    def clean(self):
        cleaned = super().clean()
        st = cleaned.get("skill_type")
        s = cleaned.get("skill")
        lv = cleaned.get("skill_level")

        # تحقق التناسق: skill/level ينتميان لنفس type
        if st and s and s.skill_type_id != st.id:
            raise ValidationError({"skill": "Skill must belong to the selected skill type."})
        if st and lv and lv.skill_type_id != st.id:
            raise ValidationError({"skill_level": "Level must belong to the selected skill type."})

        return cleaned

    def save(self, commit=True):
        """
        - إنشاء: add_skill(...)
        - تعديل: update_skill_versioned(instance, **changes)
        يعيد الكائن النهائي (الجديد في حالة التعديل).
        """
        cd = self.cleaned_data
        if not self.instance or not self.instance.pk:
            # إنشاء
            rec = add_skill(
                employee_id=cd["employee"].id,
                skill_type_id=cd["skill_type"].id,
                skill_id=cd["skill"].id,
                level_id=cd["skill_level"].id,
                valid_from=cd["valid_from"],
                valid_to=cd.get("valid_to"),
            )
            # اجعل form.instance هو المُنشأ حديثًا
            self.instance = rec
            return rec

        # تعديل (versioned)
        changes = {
            "skill_type_id": cd["skill_type"].id,
            "skill_id": cd["skill"].id,
            "skill_level_id": cd["skill_level"].id,
            "valid_from": cd["valid_from"],
            "valid_to": cd.get("valid_to"),
        }
        new_rec = update_skill_versioned(self.instance, **changes)
        self.instance = new_rec
        return new_rec


class EmployeeSkillArchiveForm(TailwindModelForm):
    """
    نموذج اختياري: لأرشفة سجل مهارة موجود (ضبط valid_to).
    يمكنك استخدامه في View منفصل كإجراء سريع.
    """
    class Meta:
        model = HrEmployeeSkill
        fields = ["valid_to"]
        widgets = {"valid_to": forms.DateInput(attrs={"type": "date"})}

    def clean_valid_to(self):
        vt = self.cleaned_data.get("valid_to")
        if not vt:
            raise ValidationError("Archive date is required.")
        return vt
