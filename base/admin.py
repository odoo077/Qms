# base/admin.py
# ============================================================
# Django Admin — company scope is relaxed inside admin (Odoo-like)
# ------------------------------------------------------------
# ملاحظة: نستخدم Mixin لإلغاء سكوب الشركات في الأدمن فقط، كي يرى المدير
# كل السجلات + كل الخيارات داخل القوائم (FK/M2M) بدون قيود الشركة.
# ============================================================

from __future__ import annotations

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.urls import reverse
from django.utils.html import format_html
from base.admin_mixins import AppAdmin, HideAuditFieldsMixin, UnscopedAdminMixin
from . import models


# ------------------------------------------------------------
# Currency
# ------------------------------------------------------------
@admin.register(models.Currency)
class CurrencyAdmin(AppAdmin):
    list_display = ("code", "name")
    search_fields = ("code", "name")
    ordering = ("code",)


# ------------------------------------------------------------
# Company
# ------------------------------------------------------------
@admin.register(models.Company)
class CompanyAdmin(AppAdmin):
    list_display = ("name", "sequence", "parent", "currency", "active", "partner_link")
    list_filter = ("active",)
    search_fields = (
        "name",
        "partner__name", "partner__email", "partner__phone",
        "partner__company_registry", "partner__vat",
    )
    list_select_related = ("parent", "partner", "currency")
    ordering = ("sequence", "name")

    autocomplete_fields = ("parent", "partner", "currency")

    readonly_fields = (
        "company_email", "company_phone",
        "company_website", "company_vat", "company_registry"
    )

    fieldsets = (
        ("Core", {"fields": ("name", "sequence", "active", "parent", "currency", "partner")}),
        ("Identity (from Partner / read-only)", {
            "fields": (
                "company_email", "company_phone",
                "company_website", "company_vat", "company_registry"
            ),
            "description": "These fields mirror the linked Partner. Edit them on the Partner record.",
        }),
    )

    def partner_link(self, obj):
        if getattr(obj, "partner_id", None):
            url = reverse("admin:base_partner_change", args=[obj.partner_id])
            return format_html('<a href="{}">Go to Partner</a>', url)
        return "-"
    partner_link.short_description = "Partner"

    def company_email(self, obj):
        return getattr(getattr(obj, "partner", None), "email", "") if obj.partner_id else ""
    company_email.short_description = "Email"

    def company_phone(self, obj):
        return getattr(getattr(obj, "partner", None), "phone", "") if obj.partner_id else ""
    company_phone.short_description = "Phone"

    def company_website(self, obj):
        return getattr(getattr(obj, "partner", None), "website", "") if obj.partner_id else ""
    company_website.short_description = "Website"

    def company_vat(self, obj):
        return getattr(getattr(obj, "partner", None), "vat", "") if obj.partner_id else ""
    company_vat.short_description = "VAT"

    def company_registry(self, obj):
        return getattr(getattr(obj, "partner", None), "company_registry", "") if obj.partner_id else ""
    company_registry.short_description = "Company Registry"


# ------------------------------------------------------------
# PartnerCategory
# ------------------------------------------------------------
@admin.register(models.PartnerCategory)
class PartnerCategoryAdmin(AppAdmin):
    list_display = ("name", "complete_name", "parent")
    search_fields = ("name", "complete_name")
    ordering = ("complete_name",)
    autocomplete_fields = ("parent",)


# ------------------------------------------------------------
# Partner
# ------------------------------------------------------------
@admin.register(models.Partner)
class PartnerAdmin(AppAdmin):
    list_display = ("display_name", "company", "company_type", "type", "phone", "mobile", "active")
    list_filter = ("company_type", "type", "active")
    search_fields = ("display_name", "name", "email", "phone", "mobile", "company_registry", "vat")
    list_select_related = ("company", "parent")
    ordering = ("display_name",)

    autocomplete_fields = ("company", "parent", "salesperson", "categories")
    readonly_fields = ("employee",)


# ------------------------------------------------------------
# UserSettings — Inline on User
# ------------------------------------------------------------
class UserSettingsInline(admin.StackedInline):
    model = models.UserSettings
    fk_name = "user"
    can_delete = False
    extra = 0
    max_num = 1

    readonly_fields = ("default_company",)

    fieldsets = (
        (None, {
            "fields": (
                "default_company",
                "tz", "lang",
                "notification_type", "signature",
                "theme", "sidebar_state",
                "redirect_after_login",
                "time_format_24h", "date_format", "show_tips",
            )
        }),
    )


# ------------------------------------------------------------
# User
# ------------------------------------------------------------
User = get_user_model()


@admin.register(User)
class UserAdmin(UnscopedAdminMixin, HideAuditFieldsMixin, DjangoUserAdmin):
    list_display = (
        "id",
        "display_name",
        "email",
        "company",
        "partner_link",
        "is_active",
        "is_staff",
        "is_superuser",
        "email_verified",
    )
    list_filter = ("is_active", "is_staff", "is_superuser", "email_verified", "company")
    search_fields = ("email", "username", "first_name", "last_name", "partner__name")
    list_select_related = ("company", "partner")
    ordering = ("-date_joined",)

    autocomplete_fields = ("company", "companies", "partner")

    readonly_fields = (
        "created_at", "updated_at",
        "last_login", "date_joined",
        "email_verified_at", "last_session_key",
    )

    fieldsets = (
        ("Identity", {"fields": ("email", "username", "password")}),
        ("Profile", {"fields": ("first_name", "last_name", "avatar", "partner")}),
        ("Company", {"fields": ("company", "companies")}),
        ("Status", {
            "fields": (
                "is_active", "is_staff", "is_superuser",
                "email_verified", "email_verified_at", "last_session_key",
                "groups", "user_permissions",
            )
        }),
        ("Timestamps", {"fields": ("created_at", "updated_at", "last_login", "date_joined")}),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": (
                "email", "username", "password1", "password2",
                "first_name", "last_name",
                "company", "companies",
                "is_active", "is_staff", "is_superuser", "groups",
            ),
        }),
    )

    inlines = [UserSettingsInline]

    def partner_link(self, obj):
        if getattr(obj, "partner_id", None):
            url = reverse("admin:base_partner_change", args=[obj.partner_id])
            return format_html('<a href="{}">Go to Partner</a>', url)
        return "-"
    partner_link.short_description = "Partner"

    def save_related(self, request, form, formsets, change):
        result = super().save_related(request, form, formsets, change)
        user = form.instance
        if getattr(user, "company_id", None) and not user.companies.filter(pk=user.company_id).exists():
            pass
        return result


# ------------------------------------------------------------
# Global admin display tweaks
# ------------------------------------------------------------
admin.site.empty_value_display = "—"
