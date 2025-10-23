from __future__ import annotations

# ============================================================
# xfields/admin.py
# تسجيل النماذج + Inline عام للربط بأي موديل
# ============================================================

from django.contrib import admin
from django.contrib.contenttypes.admin import GenericStackedInline
from .models import XField, XFieldOption, XValue


class XFieldOptionInline(admin.TabularInline):
    model = XFieldOption
    extra = 0


@admin.register(XField)
class XFieldAdmin(admin.ModelAdmin):
    list_display = ("id", "model", "company", "code", "name", "field_type", "required", "allow_multiple")
    list_filter = ("model", "company", "field_type", "required", "allow_multiple")
    search_fields = ("code", "name")
    inlines = [XFieldOptionInline]


class XValueInline(GenericStackedInline):
    """
    Inline عام يمكن تركيبه على أي Admin لعرض/تحرير قيم xfields.
    """
    model = XValue
    extra = 0
    ct_field = "content_type"
    ct_fk_field = "object_id"
    fields = ("field", "char_value", "text_value", "int_value", "float_value", "bool_value",
              "date_value", "datetime_value", "json_value")
    readonly_fields = ()
    classes = ("collapse",)


@admin.register(XValue)
class XValueAdmin(admin.ModelAdmin):
    list_display = ("id", "field", "content_type", "object_id", "short_value")
    list_filter = ("field__model", "field__company", "field__field_type")
    search_fields = ("field__code",)

    def short_value(self, obj):
        v = obj.value
        if isinstance(v, (list, tuple, set)):
            return ", ".join(map(str, v))
        return v
