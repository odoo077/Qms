from __future__ import annotations

# ============================================================
# xfields/admin.py
# تسجيل النماذج + Inline عام للربط بأي موديل
# ============================================================

from django.contrib import admin
from .models import XField, XFieldOption, XValue
from base.admin_mixins import AppAdmin
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.admin import GenericStackedInline
from .models import XValue

# ------------------------------------------------------------
# Inline لخيارات الحقول (XFieldOption)
# ------------------------------------------------------------
class XFieldOptionInline(admin.TabularInline):
    model = XFieldOption
    extra = 0


# ------------------------------------------------------------
# Inline عام لعرض قيم XValue داخل أي موديل (Generic)
# ------------------------------------------------------------

from django import forms
from .models import XValue, XField


class XValueInlineForm(forms.ModelForm):
    """نموذج ذكي يُظهر فقط الحقول المناسبة حسب نوع XField المختار."""

    class Meta:
        model = XValue
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        f = getattr(self.instance, "field", None)
        if not f:
            # الحالة الأولى: سجل جديد قبل اختيار الحقل
            for name in list(self.fields.keys()):
                if name not in {"field", "json_value"}:
                    self.fields[name].widget = forms.HiddenInput()
            return

        show_fields = {"field"}

        # نعرض فقط الحقول المرتبطة بالنوع المناسب
        if f.field_type == XField.FIELD_CHAR:
            show_fields |= {"char_value"}
        elif f.field_type == XField.FIELD_TEXT:
            show_fields |= {"text_value"}
        elif f.field_type == XField.FIELD_INT:
            show_fields |= {"int_value"}
        elif f.field_type == XField.FIELD_FLOAT:
            show_fields |= {"float_value"}
        elif f.field_type == XField.FIELD_BOOL:
            show_fields |= {"bool_value"}
        elif f.field_type == XField.FIELD_DATE:
            show_fields |= {"date_value"}
        elif f.field_type == XField.FIELD_DATETIME:
            show_fields |= {"datetime_value"}
        elif f.field_type in (XField.FIELD_CHOICE, XField.FIELD_MULTI):
            show_fields |= {"json_value"}
            opts = list(f.options.values_list("value", "label"))
            if opts:
                # ✅ Dropdown لقيم Choice المفردة
                if f.field_type == XField.FIELD_CHOICE:
                    self.fields["json_value"] = forms.ChoiceField(
                        label="Value",
                        choices=[("", "----")] + opts,
                        required=bool(f.required),
                    )
                # ✅ مربعات اختيار لقيم Multi-Choice
                elif f.field_type == XField.FIELD_MULTI:
                    self.fields["json_value"] = forms.MultipleChoiceField(
                        label="Values",
                        choices=opts,
                        required=bool(f.required),
                        widget=forms.CheckboxSelectMultiple,
                    )

        # إخفاء الحقول الأخرى
        for name in list(self.fields.keys()):
            if name not in show_fields:
                self.fields[name].widget = forms.HiddenInput()

    # ✅ نحول القيم إلى list دائمًا للأنواع choice/multi_choice
    def clean_json_value(self):
        val = self.cleaned_data.get("json_value")
        if val in (None, "", [], "null"):
            return None
        if isinstance(val, (list, tuple)):
            return list(val)
        return [val]


class XValueInline(GenericStackedInline):
    model = XValue
    form = XValueInlineForm
    extra = 0
    verbose_name = "Extra Field"
    verbose_name_plural = "Extra Fields"


    def save_formset(self, request, form, formset, change):
        """
        نحقن content_type و object_id قبل الحفظ النهائي لأي XValue جديد.
        """
        instances = formset.save(commit=False)
        ct = ContentType.objects.get_for_model(self.parent_model)
        parent = form.instance  # الموظف الحالي

        for inst in instances:
            # إذا لم تُحدد content_type أو object_id (السجلات الجديدة)
            if not inst.content_type_id:
                inst.content_type = ct
            if not inst.object_id:
                inst.object_id = parent.pk
            inst.save()

        formset.save_m2m()


# ------------------------------------------------------------
# إدارة نموذج XField
# ------------------------------------------------------------
@admin.register(XField)
class XFieldAdmin(AppAdmin):
    list_display = (
        "id", "model", "company", "code", "name",
        "field_type", "required", "allow_multiple"
    )
    list_filter = ("model", "company", "field_type", "required", "allow_multiple")
    search_fields = ("code", "name")
    inlines = [XFieldOptionInline]
    list_select_related = ("model", "company")


# ------------------------------------------------------------
# إدارة نموذج XValue
# ------------------------------------------------------------
@admin.register(XValue)
class XValueAdmin(AppAdmin):
    list_display = ("id", "field", "content_type", "object_id", "short_value")
    list_filter = ("field__model", "field__company", "field__field_type")
    search_fields = ("field__code",)
    list_select_related = ("field", "content_type")
