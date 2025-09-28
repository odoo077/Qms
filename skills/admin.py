# skills/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .models import (
    HrSkillType, HrSkillLevel, HrSkill,
    HrEmployeeSkill, HrResumeLineType, HrResumeLine
)

# ====== إعدادات عامة للوحة الإدارة (شكل احترافي) ======
admin.site.site_header = "Skills Administration"
admin.site.index_title = "Skills & Resume Management"
admin.site.site_title = "Skills Admin"


# ====== أدوات عرض مساعدة ======
def color_chip(value: int | str | None):
    """
    رسم مربع لون صغير. يقبل رقم (كود Odoo 1..11) أو HEX (#RRGGBB).
    """
    if value is None:
        return "-"
    # لو القيمة رقمية (كألوان Odoo)، نحولها إلى لون تقريبي ثابت
    palette = {
        1: "#1f77b4", 2: "#ff7f0e", 3: "#2ca02c", 4: "#d62728", 5: "#9467bd",
        6: "#8c564b", 7: "#e377c2", 8: "#7f7f7f", 9: "#bcbd22", 10: "#17becf", 11: "#444444",
    }
    hex_color = palette.get(value, str(value))
    return format_html(
        '<span title="{}" style="display:inline-block;width:14px;height:14px;border-radius:3px;'
        'border:1px solid #333;margin-right:6px;background:{};"></span>{}',
        hex_color, hex_color, hex_color
    )


# ====== Inlines لسرعة التحرير من شاشة النوع ======
class SkillInline(admin.TabularInline):
    model = HrSkill
    extra = 0
    fields = ("name", "sequence")
    show_change_link = True


class SkillLevelInline(admin.TabularInline):
    model = HrSkillLevel
    extra = 0
    fields = ("name", "level_progress", "default_level")
    show_change_link = True


# ====== Skill Type ======
@admin.register(HrSkillType)
class HrSkillTypeAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "is_certification_badge",
        "levels_count",
        "sequence",
        "active",
        "color_display",
    )
    list_filter = ("is_certification", "active")
    search_fields = ("name",)
    ordering = ("sequence", "name")
    readonly_fields = ("levels_count",)
    inlines = (SkillInline, SkillLevelInline)

    def color_display(self, obj):
        return color_chip(obj.color)
    color_display.short_description = "Color"

    def is_certification_badge(self, obj):
        return mark_safe("✅" if obj.is_certification else "—")
    is_certification_badge.short_description = "Certification?"


# ====== Skill Level ======
@admin.register(HrSkillLevel)
class HrSkillLevelAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "skill_type_name",
        "level_progress",
        "default_level_badge",
    )
    list_filter = ("skill_type", "default_level")
    search_fields = ("name", "skill_type__name")
    ordering = ("skill_type__name", "level_progress", "name")
    autocomplete_fields = ("skill_type",)
    list_select_related = ("skill_type",)
    list_display_links = ("name",)

    def skill_type_name(self, obj):
        return obj.skill_type.name if obj.skill_type_id else "-"
    skill_type_name.short_description = "Skill Type"

    def default_level_badge(self, obj):
        return mark_safe("✅" if obj.default_level else "—")
    default_level_badge.short_description = "Default"


# ====== Skill ======
@admin.register(HrSkill)
class HrSkillAdmin(admin.ModelAdmin):
    list_display = ("name", "skill_type_name", "sequence", "color_display")
    list_filter = ("skill_type",)
    search_fields = ("name", "skill_type__name")
    ordering = ("skill_type__name", "sequence", "name")
    autocomplete_fields = ("skill_type",)
    list_select_related = ("skill_type",)
    list_display_links = ("name",)

    def skill_type_name(self, obj):
        return obj.skill_type.name if obj.skill_type_id else "-"
    skill_type_name.short_description = "Skill Type"

    def color_display(self, obj):
        # اللون مأخوذ من نوع المهارة (related)
        return color_chip(getattr(obj, "color", None))
    color_display.short_description = "Color"


# ====== Employee Skill ======
@admin.register(HrEmployeeSkill)
class HrEmployeeSkillAdmin(admin.ModelAdmin):
    list_display = (
        "employee_name",
        "skill_type_name",
        "skill_name",
        "skill_level_name",
        "level_progress_col",
        "is_certification_badge",
        "valid_from",
        "valid_to",
    )
    list_filter = (
        "skill_type",
        "skill_level",
        "skill_type__is_certification",
        "valid_from",
        "valid_to",
    )
    search_fields = (
        "employee__name",
        "skill__name",
        "skill_level__name",
        "skill_type__name",
    )
    date_hierarchy = "valid_from"
    ordering = ("employee__name", "skill_type__name", "skill__name", "-valid_from")
    autocomplete_fields = ("employee", "skill_type", "skill", "skill_level")
    list_select_related = ("employee", "skill_type", "skill", "skill_level")

    fieldsets = (
        ("Employee", {"fields": ("employee",)}),
        ("Skill", {"fields": ("skill_type", "skill", "skill_level")}),
        ("Validity", {"fields": ("valid_from", "valid_to")}),
    )

    # أعمدة بأسماء واضحة حتى لو ما عندك __str__ على النماذج
    def employee_name(self, obj):
        return getattr(obj.employee, "name", obj.employee_id)
    employee_name.short_description = "Employee"

    def skill_type_name(self, obj):
        return getattr(obj.skill_type, "name", obj.skill_type_id)
    skill_type_name.short_description = "Skill Type"

    def skill_name(self, obj):
        return getattr(obj.skill, "name", obj.skill_id)
    skill_name.short_description = "Skill"

    def skill_level_name(self, obj):
        return getattr(obj.skill_level, "name", obj.skill_level_id)
    skill_level_name.short_description = "Level"

    def level_progress_col(self, obj):
        return getattr(obj.skill_level, "level_progress", None)
    level_progress_col.short_description = "Progress"

    def is_certification_badge(self, obj):
        return mark_safe("🎖️" if getattr(obj.skill_type, "is_certification", False) else "—")
    is_certification_badge.short_description = "Certification?"


# ====== Resume Line Type ======
@admin.register(HrResumeLineType)
class HrResumeLineTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "is_course_badge", "sequence")
    list_filter = ("is_course",)
    search_fields = ("name",)
    ordering = ("sequence", "name")
    list_display_links = ("name",)

    def is_course_badge(self, obj):
        return mark_safe("✅" if obj.is_course else "—")
    is_course_badge.short_description = "Is Course?"


# ====== Resume Line ======
@admin.register(HrResumeLine)
class HrResumeLineAdmin(admin.ModelAdmin):
    list_display = (
        "employee_name",
        "line_type_name",
        "name",
        "course_type",
        "date_start",
        "date_end",
        "external_url_short",
    )
    list_filter = ("line_type", "course_type", "date_start", "date_end")
    search_fields = ("name", "employee__name", "line_type__name", "external_url")
    date_hierarchy = "date_start"
    ordering = ("line_type__name", "-date_end", "-date_start", "name")
    autocomplete_fields = ("employee", "line_type")
    list_select_related = ("employee", "line_type")
    readonly_fields = ("color_preview",)

    fieldsets = (
        ("Employee & Type", {"fields": ("employee", "line_type")}),
        ("Details", {"fields": ("name", "description", "course_type", "external_url")}),
        ("Dates", {"fields": ("date_start", "date_end", "duration")}),
        ("Certificate", {"fields": ("certificate_filename", "certificate_file")}),
        ("Color", {"fields": ("color_preview",)}),
    )

    def employee_name(self, obj):
        return getattr(obj.employee, "name", obj.employee_id)
    employee_name.short_description = "Employee"

    def line_type_name(self, obj):
        return getattr(obj.line_type, "name", obj.line_type_id)
    line_type_name.short_description = "Resume Type"

    def external_url_short(self, obj):
        if not obj.external_url:
            return "-"
        return mark_safe(f'<a href="{obj.external_url}" target="_blank">Open</a>')
    external_url_short.short_description = "URL"

    def color_preview(self, obj):
        if not getattr(obj, "color", None):
            return "-"
        return format_html(
            '<div style="width:32px;height:16px;border-radius:4px;border:1px solid #333;'
            'background:{};"></div>', obj.color
        )
    color_preview.short_description = "Color"
