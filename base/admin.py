# base/admin.py
# ============================================================
# Django Admin — company scope is relaxed inside admin (Odoo-like)
# ------------------------------------------------------------
# ملاحظة: نستخدم Mixin لإلغاء سكوب الشركات في الأدمن فقط، كي يرى المدير
# كل السجلات + كل الخيارات داخل القوائم (FK/M2M) بدون قيود الشركة.
# ============================================================

from __future__ import annotations

from typing import Any
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.urls import reverse
from django.utils.html import format_html

from . import models


# ------------------------------------------------------------
# Helper — pick an unscoped manager for a given model
# ------------------------------------------------------------
def _unscoped_manager(model: type) -> Any:
    # محاولة استخدام all_objects إن توفّر، وإلّا _base_manager (غير مقيّد)
    return getattr(model, "all_objects", model._base_manager)


# ------------------------------------------------------------
# Mixin — un-scope queries only inside the Django Admin
# ------------------------------------------------------------
class UnscopedAdminMixin:
    # اجلب كل السجلات (بدون سكوب الشركة) في قوائم الأدمن
    def get_queryset(self, request):
        return _unscoped_manager(self.model).all()

    # اجعل حقول FK تعرض كل الخيارات (بدون سكوب)
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        Remote = db_field.remote_field.model
        kwargs.setdefault("queryset", _unscoped_manager(Remote).all())
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    # اجعل حقول M2M تعرض كل الخيارات (بدون سكوب)
    def formfield_for_manytomany(self, db_field, request, **kwargs):
        Remote = db_field.remote_field.model
        kwargs.setdefault("queryset", _unscoped_manager(Remote).all())
        return super().formfield_for_manytomany(db_field, request, **kwargs)


# ------------------------------------------------------------
# Currency
# ------------------------------------------------------------
@admin.register(models.Currency)
class CurrencyAdmin(UnscopedAdminMixin, admin.ModelAdmin):
    # ✅ المتاح في الموديل فعليًا: code, name
    list_display = ("code", "name")  # الحقول الفعلية فقط (إزالة symbol/active)
    search_fields = ("code", "name")
    ordering = ("code",)


# ------------------------------------------------------------
# Company
# ------------------------------------------------------------
@admin.register(models.Company)
class CompanyAdmin(UnscopedAdminMixin, admin.ModelAdmin):
    # عرض سريع + رابط إلى بطاقة الشريك
    list_display = ("name", "sequence", "parent", "currency", "active", "partner_link")
    list_filter = ("active",)
    search_fields = (
        "name",
        "partner__name", "partner__email", "partner__phone",
        "partner__company_registry", "partner__vat",
    )
    list_select_related = ("parent", "partner", "currency")
    ordering = ("sequence", "name")

    # واجهة اختيار سلسة (autocomplete) للعلاقات الكبيرة
    autocomplete_fields = ("parent", "partner", "currency")

    # حقول read-only من بطاقة الشريك (تُعرض للمرجعية فقط)
    readonly_fields = ("company_email", "company_phone", "company_website", "company_vat", "company_registry")

    fieldsets = (
        ("Core", {"fields": ("name", "sequence", "active", "parent", "currency", "partner")}),  # الحقول الأساسية
        ("Identity (from Partner / read-only)", {  # حقول منسوخة من Partner للعرض فقط
            "fields": ("company_email", "company_phone", "company_website", "company_vat", "company_registry"),
            "description": "These fields mirror the linked Partner. Edit them on the Partner record.",
        }),
    )

    # رابط سريع إلى Partner
    # يعرض زرًا “Go to Partner” يفتح سجل الشريك في الأدمن
    def partner_link(self, obj):
        # رابط إلى شاشة تعديل الـ Partner المرتبط بالشركة
        # (لو ماكو Partner يرجّع "-")
        if getattr(obj, "partner_id", None):
            url = reverse("admin:base_partner_change", args=[obj.partner_id])
            return format_html('<a href="{}">Go to Partner</a>', url)
        return "-"
    partner_link.short_description = "Partner"

    # حقول read-only من Partner (اقتباس للعرض فقط)
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
# PartnerCategory  ← NEW: required for Partner.autocomplete_fields["categories"]
# ------------------------------------------------------------
@admin.register(models.PartnerCategory)
class PartnerCategoryAdmin(UnscopedAdminMixin, admin.ModelAdmin):
    # لعرض واضح عبر الشجرة + دعم البحث للأوتوكومبليت
    list_display = ("name", "complete_name", "parent")
    search_fields = ("name", "complete_name")
    ordering = ("complete_name",)
    autocomplete_fields = ("parent",)


# ------------------------------------------------------------
# Partner
# ------------------------------------------------------------
@admin.register(models.Partner)
class PartnerAdmin(UnscopedAdminMixin, admin.ModelAdmin):
    list_display = ("display_name", "company", "company_type", "type", "active")
    list_filter = ("company_type", "type", "active")
    search_fields = ("display_name", "name", "email", "phone", "company_registry", "vat")
    list_select_related = ("company", "parent")
    ordering = ("display_name",)

    # تحسين تجربة اختيار العلاقات الكبيرة
    autocomplete_fields = ("company", "parent", "salesperson", "categories")  # categories = M2M chips-like
    # ملاحظة: تفعيل autocomplete يتطلّب search_fields في Admin للنماذج الهدف (موجود الآن في PartnerCategoryAdmin وCompanyAdmin وغيرها)


# ------------------------------------------------------------
# UserSettings — Inline on User
# ------------------------------------------------------------
class UserSettingsInline(admin.StackedInline):
    # عرض إعدادات المستخدم ضمن نفس شاشة المستخدم (Inline)
    model = models.UserSettings
    fk_name = "user"
    can_delete = False
    extra = 0
    max_num = 1

    # افتراضيًا، اجعل default_company للقراءة فقط لأن المنطق يحكمه User.company
    # (يمكنك فتحه إن رغبت بتحريره يدويًا)
    readonly_fields = ("default_company",)

    fieldsets = (
        (None, {  # إعدادات عامة
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
# User (extends Django's UserAdmin)
# ------------------------------------------------------------
User = get_user_model()


@admin.register(User)
class UserAdmin(UnscopedAdminMixin, DjangoUserAdmin):
    """
    User admin with:
      - unscoped queries inside admin
      - M2M 'companies' as Select2 chips via autocomplete_fields
      - inline UserSettings
      - quick link to Partner
    """
    # قائمة الأعمدة + عمود رابط سريع إلى Partner
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

    # (1) واجهة M2M كـ chips عبر select2 — شرط وجود search_fields في CompanyAdmin
    #     هذا يلبّي رغبتك في اختيارات “طافية” سهلة الإضافة/الإزالة بلا فقدان القيم السابقة.
    autocomplete_fields = ("company", "companies", "partner")

    # الحقول للقراءة فقط
    readonly_fields = ("created_at", "updated_at", "last_login", "date_joined", "email_verified_at", "last_session_key")

    # المجموعات (عناوين بالإنجليزية فقط؛ التعليقات بالعربية)
    fieldsets = (
        ("Identity", {"fields": ("email", "username", "password")}),  # الهوية
        ("Profile", {"fields": ("first_name", "last_name", "avatar", "partner")}),  # الملف
        ("Company", {"fields": ("company", "companies")}),  # الشركات (افتراضية + مسموح بها)
        ("Status", {  # الحالة والصلاحيات
            "fields": (
                "is_active", "is_staff", "is_superuser",
                "email_verified", "email_verified_at", "last_session_key",
                "groups", "user_permissions",
            )
        }),
        ("Timestamps", {"fields": ("created_at", "updated_at", "last_login", "date_joined")}),  # الطوابع الزمنية
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

    # أضف الـ inline الخاص بإعدادات المستخدم
    inlines = [UserSettingsInline]

    # رابط سريع إلى بطاقة الشريك من قائمة المستخدمين
    def partner_link(self, obj):
        # زر “Go to Partner” يفتح سجل الـ Partner المرتبط بالمستخدم
        if getattr(obj, "partner_id", None):
            url = reverse("admin:base_partner_change", args=[obj.partner_id])
            return format_html('<a href="{}">Go to Partner</a>', url)
        return "-"
    partner_link.short_description = "Partner"

    # ضمان بقاء الشركة الافتراضية ضمن المسموح بها حتى لو نسي الأدمن إضافتها
    def save_related(self, request, form, formsets, change):
        """
        تأكيد أن user.company ضمن user.companies قبل تنفيذ الحفظ لعلاقات M2M.
        """
        result = super().save_related(request, form, formsets, change)
        user = form.instance
        if getattr(user, "company_id", None) and not user.companies.filter(pk=user.company_id).exists():
            user.companies.add(user.company_id)
        return result


# ------------------------------------------------------------
# Global admin display tweaks
# ------------------------------------------------------------
# قيمة العرض الافتراضية للحقل الفارغ
admin.site.empty_value_display = "—"
