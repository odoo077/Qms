# -*- coding: utf-8 -*-
"""
صفحات الإدارة لتطبيق الأصول (assets)
- تعتمد على base.admin_mixins.AppAdmin الذي:
  * يعرض كل السجلات بدون سكوبات شركات (UnscopedAdminMixin)
  * يُخفي حقول الأثر (HideAuditFieldsMixin)
  * يستثني صفحة الإدارة من صلاحيات Guardian على مستوى الكائن
- الكود منسق ومبسّط لأقصى أداء.
"""

from django.contrib import admin, messages
from django.utils.translation import gettext_lazy as _

from base.admin import ObjectACLInline
from base.admin_mixins import AppAdmin  # ✅ الميكسن النهائي للاستثناء من صلاحيات الكائن
from . import models as m


# ============================================================
# أكشنات عامة بسيطة (تفعيل / تعطيل)
# ============================================================

@admin.action(description=_("Activate selected"))
def action_activate(modeladmin, request, queryset):
    """تفعيل السجلات المحددة بدون المرور بـ save()."""
    updated = queryset.update(active=True)
    modeladmin.message_user(request, f"Activated {updated} record(s).", level=messages.SUCCESS)


@admin.action(description=_("Deactivate selected"))
def action_deactivate(modeladmin, request, queryset):
    """تعطيل السجلات المحددة بدون المرور بـ save()."""
    updated = queryset.update(active=False)
    modeladmin.message_user(request, f"Deactivated {updated} record(s).", level=messages.SUCCESS)


# ============================================================
# AssetCategory
# ============================================================

@admin.register(m.AssetCategory)
class AssetCategoryAdmin(AppAdmin):
    """
    إدارة فئات الأصول (assets.category)
    - تعرض جميع الفئات لكل الشركات.
    """
    list_display = ("name", "company", "parent", "active")
    list_filter = ("company", "active")
    search_fields = ("name", "parent__name")
    list_select_related = ("company", "parent")
    ordering = ("company", "name")
    autocomplete_fields = ("company", "parent")
    actions = (action_activate, action_deactivate)


# ============================================================
# Asset
# ============================================================


@admin.register(m.Asset)
class AssetAdmin(AppAdmin):

    inlines = [ObjectACLInline]

    """
    إدارة الأصول (assets.asset)
    - مستثنى من صلاحيات Guardian على مستوى الكائن.
    """
    list_display = (
        "code", "name", "company", "category", "department",
        "holder", "status", "active",
    )
    list_filter = ("company", "status", "active", "category")
    search_fields = ("code", "name", "serial", "holder__name", "department__name")
    list_select_related = ("company", "category", "department", "holder")
    ordering = ("company", "code", "name")
    autocomplete_fields = ("company", "category", "department", "holder")
    readonly_fields = ("created_by", "created_at", "updated_at")
    actions = (action_activate, action_deactivate)

    def save_model(self, request, obj, form, change):
        if not change and not obj.created_by_id and request.user.is_authenticated:
            obj.created_by = request.user
        if request.user.is_authenticated:
            obj.updated_by = request.user
        super().save_model(request, obj, form, change)


# ============================================================
# AssetAssignment
# ============================================================

@admin.register(m.AssetAssignment)
class AssetAssignmentAdmin(AppAdmin):
    """
    إدارة سجلات إسناد الأصول (assets.assignment)
    - تعرض كل السجلات دون تقييد صلاحيات الكائن.
    """
    list_display = ("asset", "employee", "company", "date_from", "date_to", "active")
    list_filter = ("company", "active")
    search_fields = ("asset__code", "asset__name", "employee__name")
    list_select_related = ("asset", "employee", "company")
    ordering = ("-id",)
    autocomplete_fields = ("asset", "employee", "company")
    actions = (action_activate, action_deactivate)

    readonly_fields = ("company",)
