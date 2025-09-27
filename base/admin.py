# base/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import Company, Currency, PartnerCategory, Partner, User, UserSettings

@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = ("code", "name")
    search_fields = ("code", "name")

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "sequence", "parent", "currency", "active")
    ordering = ("sequence", "name")
    list_filter = ("active",)
    search_fields = ("name", "company_registry", "vat")


@admin.register(PartnerCategory)
class PartnerCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "parent")
    search_fields = ("name",)

@admin.register(Partner)
class PartnerAdmin(admin.ModelAdmin):
    list_display = ("display_name", "company", "company_type", "type", "active")
    list_filter = ("company_type", "type", "active")
    search_fields = ("display_name", "name", "email", "vat", "company_registry")
    autocomplete_fields = ("parent", "company", "salesperson", "categories")

class UserSettingsInline(admin.StackedInline):
    model = UserSettings
    can_delete = False
    extra = 0
    fk_name = "user"
    fieldsets = (
        (None, {"fields": (
            "default_company", "tz", "lang",
            "notification_type", "signature", "theme", "sidebar_state",
            "redirect_after_login", "time_format_24h", "date_format", "show_tips"
        )}),
    )

@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    model = User
    list_display = ("id", "display_name", "email", "company", "is_active", "active", "is_staff", "is_superuser", "email_verified")
    list_filter = ("is_active", "active", "is_staff", "is_superuser", "email_verified")
    search_fields = ("email", "username", "first_name", "last_name", "partner__name")
    ordering = ("-date_joined",)
    readonly_fields = ("created_at", "updated_at", "last_login", "date_joined", "email_verified_at", "last_session_key")
    filter_horizontal = ("companies", "groups", "user_permissions")

    fieldsets = (
        (None, {"fields": ("email", "username", "password")}),
        ("Identity", {"fields": ("first_name", "last_name", "avatar", "partner")}),
        ("Company", {"fields": ("company", "companies")}),
        ("Status", {"fields": ("is_active", "active", "is_staff", "is_superuser",
                               "email_verified", "email_verified_at", "last_session_key")}),
        ("Permissions", {"fields": ("groups", "user_permissions")}),
        ("Timestamps", {"fields": ("created_at", "updated_at", "last_login", "date_joined")}),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "username", "password1", "password2",
                       "first_name", "last_name", "company", "companies",
                       "is_active", "active", "is_staff", "is_superuser", "groups"),
        }),
    )

    inlines = [UserSettingsInline]
