# skills/admin.py
# ============================================================
# Django Admin for Skills app (Odoo-like, object-perms EXEMPT)
# - يستخدم base.admin_mixins.AppAdmin لاستثناء الأدمن من صلاحيات الكائن
# - تحسينات أداء: select_related / autocomplete_fields
# - تعليقات عربية، والكود بالإنجليزية
# ============================================================

from __future__ import annotations

from django.contrib import admin, messages

# نستخدم AppAdmin من base/admin_mixins.py لعرض كل السجلات بدون سكوبات/صلاحيات كائن
from base.admin_mixins import AppAdmin

from . import models
from base.admin import ObjectACLInline


# ============================================================
# أكشنات عامة بسيطة (تفعيل/تعطيل)
# ============================================================

@admin.action(description="Activate selected")
def action_activate(modeladmin, request, queryset):
    """أكشن سريع لتفعيل السجلات المحددة (لا يمرّ عبر save())."""
    updated = queryset.update(active=True)
    modeladmin.message_user(request, f"Activated {updated} record(s).", level=messages.SUCCESS)


@admin.action(description="Deactivate selected")
def action_deactivate(modeladmin, request, queryset):
    """أكشن سريع لتعطيل السجلات المحددة (لا يمرّ عبر save())."""
    updated = queryset.update(active=False)
    modeladmin.message_user(request, f"Deactivated {updated} record(s).", level=messages.SUCCESS)


# ============================================================
# SkillType
# ============================================================

@admin.register(models.SkillType)
class SkillTypeAdmin(AppAdmin):
    """
    نوع المهارة (hr.skill.type)
    - يظهر عدد المستويات levels_count كقيمة محسوبة (readonly).
    - هذا الأدمن مستثنى من صلاحيات الكائن بفضل AppAdmin (UnscopedAdminMixin).
    """
    list_display = ("name", "sequence", "is_certification", "levels_count", "active")
    list_filter = ("active", "is_certification")
    search_fields = ("name",)
    ordering = ("sequence", "name")
    readonly_fields = ("levels_count",)
    actions = (action_activate, action_deactivate)


# ============================================================
# SkillLevel
# ============================================================

@admin.register(models.SkillLevel)
class SkillLevelAdmin(AppAdmin):
    """
    مستوى المهارة (hr.skill.level)
    - فلاتر حسب النوع، الحالة، الافتراضي.
    - مستثنى من صلاحيات الكائن عبر AppAdmin.
    """
    list_display = ("name", "skill_type", "level_progress", "default_level", "active")
    list_filter = ("skill_type", "default_level", "active")
    search_fields = ("name", "skill_type__name")
    list_select_related = ("skill_type",)
    ordering = ("skill_type__sequence", "level_progress", "name")
    autocomplete_fields = ("skill_type",)
    actions = (action_activate, action_deactivate)


# ============================================================
# Skill
# ============================================================

@admin.register(models.Skill)
class SkillAdmin(AppAdmin):
    """
    مهارة ضمن نوع (hr.skill)
    - مستثنى من صلاحيات الكائن عبر AppAdmin.
    """
    list_display = ("name", "skill_type", "sequence", "active")
    list_filter = ("skill_type", "active")
    search_fields = ("name", "skill_type__name")
    list_select_related = ("skill_type",)
    ordering = ("skill_type__sequence", "sequence", "name")
    autocomplete_fields = ("skill_type",)
    actions = (action_activate, action_deactivate)


# ============================================================
# EmployeeSkill — EXEMPT from object-level perms in Admin
# ============================================================

@admin.register(models.EmployeeSkill)
class EmployeeSkillAdmin(AppAdmin):

    inlines = (ObjectACLInline,)

    """
    مهارة موظف (hr.employee.skill)
    - الأدمن هنا مستثنى من صلاحيات الكائن (يعرض كل شيء)، بفضل AppAdmin.
    - الأداء: select_related + autocomplete_fields.
    - الشركة تظهر للقراءة فقط (تُملأ تلقائيًا من الموظف في models.py).
    """
    list_display = (
        "employee", "company",
        "skill_type", "skill", "skill_level",
        "valid_from", "valid_to",
        "active",
    )
    list_filter = ("company", "skill_type", "skill_level", "active")
    search_fields = (
        "employee__name", "employee__work_contact__name",
        "skill__name", "skill_type__name",
    )
    list_select_related = (
        "employee", "employee__company",
        "company", "skill_type", "skill", "skill_level",
    )
    ordering = ("employee__company__name", "employee__name", "skill_type__sequence", "skill__name")
    autocomplete_fields = ("employee", "skill_type", "skill", "skill_level")
    actions = (action_activate, action_deactivate)

    # الشركة للقراءة فقط
    readonly_fields = ("company",)

    # تضمين الشركة في النموذج لتظهر للقراءة فقط (أول حقل)
    def get_fields(self, request, obj=None):
        base = [
            "employee",
            "skill_type", "skill", "skill_level",
            "valid_from", "valid_to",
            "note", "active",
        ]
        return ["company"] + base


# ============================================================
# ResumeLineType
# ============================================================

@admin.register(models.ResumeLineType)
class ResumeLineTypeAdmin(AppAdmin):
    """
    نوع سطر السيرة (hr.resume.line.type)
    - مستثنى من صلاحيات الكائن عبر AppAdmin.
    """
    list_display = ("name", "sequence", "active")
    list_filter = ("active",)
    search_fields = ("name",)
    ordering = ("sequence", "name")
    actions = (action_activate, action_deactivate)


# ============================================================
# ResumeLine — EXEMPT from object-level perms in Admin
# ============================================================

@admin.register(models.ResumeLine)
class ResumeLineAdmin(AppAdmin):

    inlines = (ObjectACLInline,)

    """
    سطر سيرة موظف (hr.resume.line)
    - الأدمن هنا مستثنى من صلاحيات الكائن (يعرض كل شيء)، بفضل AppAdmin.
    - الشركة تظهر للقراءة فقط (تُملأ تلقائيًا من الموظف في models.py).
    """
    list_display = ("employee", "company", "line_type", "name", "date_start", "date_end", "active")
    list_filter = ("company", "line_type", "active")
    search_fields = ("employee__name", "line_type__name", "name", "description")
    list_select_related = ("employee", "employee__company", "company", "line_type")
    ordering = ("employee__company__name", "employee__name", "line_type__sequence", "-date_start", "name")
    autocomplete_fields = ("employee", "line_type")
    actions = (action_activate, action_deactivate)

    # الشركة للقراءة فقط
    readonly_fields = ("company",)

    # تضمين الشركة في النموذج لتظهر للقراءة فقط (أول حقل)
    def get_fields(self, request, obj=None):
        base = [
            "employee",
            "line_type",
            "name", "description",
            "date_start", "date_end",
            "certificate_file", "certificate_filename",
            "external_url",
            "active",
        ]
        return ["company"] + base
