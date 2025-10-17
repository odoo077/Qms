# base/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.urls import reverse
from django.utils.html import format_html
from .models import Company, Currency, PartnerCategory, Partner, User, UserSettings

@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = ("code", "name")
    search_fields = ("code", "name")

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    save_as = False

    # عرض القائمة
    list_display = ("name", "sequence", "parent", "currency", "active", "partner_link")
    ordering = ("sequence", "name")
    list_filter = ("active",)
    search_fields = ("name", "partner__company_registry", "partner__vat",
                     "partner__email", "partner__phone")
    list_select_related = ("parent", "partner", "currency")

    # أوتوكومبليت للحقول العلائقية
    autocomplete_fields = ("parent", "partner", "currency")

    # حقول للقراءة فقط من بطاقة الشريك
    readonly_fields = ("company_email", "company_phone",
                       "company_website", "company_vat", "company_registry")

    fieldsets = (
        ("Core", {
            "fields": ("name", "sequence", "active", "parent", "currency", "partner"),
        }),
        ("Identity (from Partner / read-only)", {
            "fields": ("company_email", "company_phone", "company_website",
                       "company_vat", "company_registry"),
            "description": "These fields mirror the linked Partner. Edit them on the Partner, not here.",
        }),
    )

    # ✅ (اختياري لكنه مفيد) اجعل قائمة السجلات غير مقيّدة بسكوب الشركة أيضًا
    def get_queryset(self, request):
        # إن وُجد مدير غير مقيّد all_objects استخدمه، وإلا فـ objects
        qs = getattr(Company, "all_objects", Company.objects).all()
        return qs.select_related("parent", "partner", "currency")

    # رابط سريع إلى بطاقة الشريك
    def partner_link(self, obj):
        if obj.partner_id:
            url = reverse("admin:base_partner_change", args=[obj.partner_id])
            return format_html('<a href="{}">Open Partner</a>', url)
        return "-"
    partner_link.short_description = "Partner"

    # حقول القراءة فقط المنسوخة من بطاقة الشريك
    def company_email(self, obj):
        return getattr(obj.partner, "email", "") if obj.partner_id else ""
    company_email.short_description = "Email"

    def company_phone(self, obj):
        return getattr(obj.partner, "phone", "") if obj.partner_id else ""
    company_phone.short_description = "Phone"

    def company_website(self, obj):
        return getattr(obj.partner, "website", "") if obj.partner_id else ""
    company_website.short_description = "Website"

    def company_vat(self, obj):
        return getattr(obj.partner, "vat", "") if obj.partner_id else ""
    company_vat.short_description = "VAT"

    def company_registry(self, obj):
        return getattr(obj.partner, "company_registry", "") if obj.partner_id else ""
    company_registry.short_description = "Company Registry"

    # ✅ المفتاح للحل: فكّ تقييد الـ queryset لحقلي parent و partner داخل نموذج الأدمن
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "parent":
            # اسمح برؤية/اختيار أي شركة كأب (حتى لو من شركة/سكوب مختلف)
            CompanyModel = Company
            kwargs["queryset"] = getattr(CompanyModel, "all_objects", CompanyModel.objects).all()
        elif db_field.name == "partner":
            # اسمح برؤية/اختيار أي Partner (بطاقة شركة)
            from .models import Partner as PartnerModel
            kwargs["queryset"] = getattr(PartnerModel, "all_objects", PartnerModel.objects).all()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(PartnerCategory)
class PartnerCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "parent")
    search_fields = ("name",)

@admin.register(Partner)
class PartnerAdmin(admin.ModelAdmin):
    list_display = ("display_name", "company", "company_type", "type", "active")
    list_filter = ("company","company_type", "type", "active")
    search_fields = ("display_name", "name", "email", "vat", "company_registry")
    autocomplete_fields = ("parent", "company", "salesperson", "categories")
    list_select_related = ("company", "parent", "salesperson")
    ordering = ("display_name",)

    def get_queryset(self, request):
        # استخدم المدير غير المقيّد تمامًا كي يظهر Parent حتى إن كان من شركة أخرى
        return Partner.all_objects.all().select_related("company", "parent", "salesperson")

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Parent يجب أن يرى جميع الـ Partners (خصوصًا بطاقات الشركات عبر الشركات)
        if db_field.name == "parent":
            from .models import Partner as PartnerModel
            kwargs["queryset"] = PartnerModel.all_objects.all()
        # Company أيضًا نعرض كل الشركات (بدون قيود سكوب) عند التحرير من الأدمن
        if db_field.name == "company":
            from .models import Company as CompanyModel
            qs = CompanyModel.all_objects.all() if hasattr(CompanyModel, "all_objects") else CompanyModel.objects.all()
            kwargs["queryset"] = qs
        return super().formfield_for_foreignkey(db_field, request, **kwargs)



class UserSettingsInline(admin.StackedInline):
    model = UserSettings
    fk_name = "user"
    can_delete = False
    extra = 0
    max_num = 1

    # Odoo-like: default_company يعكس User.company؛ التحرير يتم من شاشة المستخدم فقط
    readonly_fields = ("default_company",)

    fieldsets = (
        (None, {"fields": (
            "default_company",  # عرض فقط (مصدره User.company)
            "tz", "lang",
            "notification_type", "signature", "theme", "sidebar_state",
            "redirect_after_login", "time_format_24h", "date_format", "show_tips"
        )}),
    )


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    model = User
    list_display = ("id", "display_name", "email", "company", "active", "is_staff", "is_superuser", "email_verified")
    list_filter = ( "active", "is_staff", "is_superuser", "email_verified")
    search_fields = ("email", "username", "first_name", "last_name", "partner__name")
    ordering = ("-date_joined",)
    readonly_fields = ("created_at", "updated_at", "last_login", "date_joined", "email_verified_at", "last_session_key")
    filter_horizontal = ("companies", "groups", "user_permissions")
    autocomplete_fields = ("company", "partner", "companies")
    list_select_related = ("company", "partner")

    fieldsets = (
        (None, {"fields": ("email", "username", "password")}),
        ("Identity", {"fields": ("first_name", "last_name", "avatar", "partner")}),
        ("Company", {"fields": ("company", "companies")}),
        ("Status", {"fields": ( "active", "is_staff", "is_superuser",
                               "email_verified", "email_verified_at", "last_session_key")}),
        ("Permissions", {"fields": ("groups", "user_permissions")}),
        ("Timestamps", {"fields": ("created_at", "updated_at", "last_login", "date_joined")}),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "username", "password1", "password2",
                       "first_name", "last_name", "company", "companies",
                     "active", "is_staff", "is_superuser", "groups"),
        }),
    )

    inlines = [UserSettingsInline]

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # اسمح باختيار أي شركة كـ default company حتى لو لم تُضَف بعد إلى allowed
        if db_field.name == "company":
            from base.models import Company
            kwargs["queryset"] = Company.all_objects.all() if hasattr(Company, "all_objects") else Company.objects.all()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_related(self, request, form, formsets, change):
        """
        Odoo-like: تأكد قبل save_m2m أن الشركة الافتراضية موجودة ضمن
        cleaned_data['companies'] حتى لا يحاول الـ Admin إزالتها.
        """
        obj = form.instance  # الـ User الذي تم حفظه للتوّ

        # إن كانت هناك شركة افتراضية معيّنة
        if getattr(obj, "company_id", None) is not None:
            comps = form.cleaned_data.get("companies", None)

            # جهّز قائمة المعرفات المختارة في الفورم (قد تكون None/QuerySet/قائمة)
            if comps is None:
                selected_ids = []
            else:
                try:
                    # ModelMultipleChoiceField عادةً ترجع QuerySet
                    selected_ids = list(comps.values_list("pk", flat=True))
                except Exception:
                    # fallback: قائمة/iterable من الكائنات
                    selected_ids = [getattr(c, "pk", c) for c in comps]

            # أضِف الشركة الافتراضية إن لم تكن موجودة ضمن المختار
            if obj.company_id not in selected_ids:
                selected_ids.append(obj.company_id)

            # أعِد حقن القيمة المعدّلة في cleaned_data قبل أن ينفّذ form.save_m2m()
            from base.models import Company
            form.cleaned_data["companies"] = Company.objects.filter(pk__in=selected_ids)

        # الآن نفّذ سلوك Django الافتراضي (سيستخدم cleaned_data المحدّثة)
        return super().save_related(request, form, formsets, change)
