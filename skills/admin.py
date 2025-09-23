from django.contrib import admin
from .models import (
    HrSkillType, HrSkillLevel, HrSkill,
    HrEmployeeSkill, HrResumeLineType, HrResumeLine
)

# ---------- Inlines ----------


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


# ---------- Skill Type ----------

@admin.register(HrSkillType)
class HrSkillTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "is_certification", "levels_count", "sequence", "active", "color")
    list_filter = ("is_certification", "active")
    search_fields = ("name",)
    ordering = ("sequence", "name")
    readonly_fields = ("levels_count",)
    inlines = (SkillInline, SkillLevelInline)


# ---------- Skill Level ----------

@admin.register(HrSkillLevel)
class HrSkillLevelAdmin(admin.ModelAdmin):
    list_display = ("name", "skill_type", "level_progress", "default_level")
    list_filter = ("skill_type", "default_level")
    search_fields = ("name",)
    ordering = ("skill_type", "level_progress", "name")
    autocomplete_fields = ("skill_type",)


# ---------- Skill ----------

@admin.register(HrSkill)
class HrSkillAdmin(admin.ModelAdmin):
    list_display = ("name", "skill_type", "sequence")
    list_filter = ("skill_type",)
    search_fields = ("name",)
    ordering = ("skill_type", "sequence", "name")
    autocomplete_fields = ("skill_type",)


# ---------- Employee Skill ----------

# skills/admin.py

@admin.register(HrEmployeeSkill)
class HrEmployeeSkillAdmin(admin.ModelAdmin):
    # ONE list_display only
    list_display = (
        "employee", "skill_type", "skill", "skill_level",
        "is_certification", "valid_from", "valid_to",
    )

    # filter by the related field (not a local field)
    list_filter = ("skill_type", "skill_level", "skill_type__is_certification")

    search_fields = ("employee__name", "skill__name", "skill_level__name")
    date_hierarchy = "valid_from"
    ordering = ("employee", "skill_type", "skill", "-valid_from")
    autocomplete_fields = ("employee", "skill_type", "skill", "skill_level")
    list_select_related = ("employee", "skill_type", "skill", "skill_level")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("employee", "skill_type", "skill", "skill_level")

    # display a boolean column derived from the related field
    def is_certification(self, obj):
        return bool(getattr(obj.skill_type, "is_certification", False))
    is_certification.boolean = True
    is_certification.admin_order_field = "skill_type__is_certification"
    is_certification.short_description = "Certification?"


# ---------- Resume Line Type ----------

@admin.register(HrResumeLineType)
class HrResumeLineTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "is_course", "sequence")
    list_filter = ("is_course",)
    search_fields = ("name",)
    ordering = ("sequence", "name")


# ---------- Resume Line ----------

@admin.register(HrResumeLine)
class HrResumeLineAdmin(admin.ModelAdmin):
    list_display = (
        "employee", "line_type", "name", "course_type",
        "date_start", "date_end", "external_url"
    )
    list_filter = ("line_type", "course_type", "date_start", "date_end")
    search_fields = ("name", "employee__name", "external_url")
    date_hierarchy = "date_start"
    ordering = ("line_type", "-date_end", "-date_start", "name")
    autocomplete_fields = ("employee", "line_type")
    readonly_fields = ("color",)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("employee", "line_type")
