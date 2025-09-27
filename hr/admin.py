# hr/admin.py
from django.contrib import admin, messages
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.urls import reverse

from .models import (
    Department,
    Employee,
    EmployeeCategory,
    ContractType,
    WorkLocation,
    Job,
)

# ========= أدوات مشتركة =========

class _StampedAdmin(admin.ModelAdmin):
    """
    عرض حقول التدقيق (created_by/updated_by) كحقول للقراءة فقط،
    مع تعبئتها تلقائيًا أثناء الحفظ.
    """
    readonly_fields = ("created_by", "updated_by", "created_at", "updated_at")

    def save_model(self, request, obj, form, change):
        # تعبئة حقول التدقيق تلقائيًا
        if not getattr(obj, "created_by_id", None):
            try:
                obj.created_by = request.user
            except Exception:
                pass
        try:
            obj.updated_by = request.user
        except Exception:
            pass
        super().save_model(request, obj, form, change)


class _ActiveActionsMixin:
    """إجراءات تفعيل/تعطيل جماعية."""
    @admin.action(description=_("Mark selected as Active"))
    def action_activate(self, request, queryset):
        updated = queryset.update(active=True)
        self.message_user(request, _("%(n)d record(s) activated.") % {"n": updated}, messages.SUCCESS)

    @admin.action(description=_("Mark selected as Inactive"))
    def action_deactivate(self, request, queryset):
        updated = queryset.update(active=False)
        self.message_user(request, _("%(n)d record(s) deactivated.") % {"n": updated}, messages.SUCCESS)

# ========= Department =========

@admin.register(Department)
class DepartmentAdmin(_StampedAdmin, _ActiveActionsMixin):
    list_display = (
        "link_complete_name", "company", "parent", "manager",
        "total_employee", "active",
    )
    list_display_links = ("link_complete_name",)
    list_filter = ("company", "active")
    search_fields = ("name", "complete_name")
    autocomplete_fields = ("manager", "parent")
    readonly_fields = _StampedAdmin.readonly_fields + ("complete_name", "parent_path", "total_employee")
    ordering = ("company", "complete_name")
    list_per_page = 50
    list_select_related = ("company", "parent", "manager")
    actions = ("action_activate", "action_deactivate")

    fieldsets = (
        (_("General"), {
            "fields": ("active", "name", "company", "parent", "manager"),
        }),
        (_("Computed"), {
            "classes": ("collapse",),
            "fields": ("complete_name", "parent_path", "total_employee"),
        }),
        (_("Audit"), {
            "classes": ("collapse",),
            "fields": ("created_by", "created_at", "updated_by", "updated_at"),
        }),
        (_("Notes"), {
            "classes": ("collapse",),
            "fields": ("note", "color"),
        }),
    )

    @admin.display(description=_("Complete name"), ordering="complete_name")
    def link_complete_name(self, obj):
        url = reverse("admin:hr_department_change", args=[obj.pk])
        return format_html('<a href="{}">{}</a>', url, obj.complete_name or obj.name)

# ========= Employee =========

class EmployeeCategoryInline(admin.TabularInline):
    model = Employee.categories.through
    extra = 0
    verbose_name = _("Category")
    verbose_name_plural = _("Categories")

@admin.register(Employee)
class EmployeeAdmin(_StampedAdmin, _ActiveActionsMixin):
    list_display = (
        "link_name", "company", "department", "job",
        "manager", "work_location", "work_contact",
        "active",
    )
    list_display_links = ("link_name",)
    list_filter = (
        "company", "department", "job", "work_location", "active",
        ("categories", admin.RelatedOnlyFieldListFilter),
    )
    search_fields = (
        "name", "work_email", "work_phone", "mobile_phone",
        "user__email", "work_contact__display_name",
    )
    autocomplete_fields = ("user", "department", "job", "manager", "coach", "work_contact", "work_location")
    raw_id_fields = ("user", "work_contact")
    ordering = ("company", "name")
    list_per_page = 50
    list_select_related = ("company", "department", "job", "manager", "coach", "work_location", "work_contact")
    inlines = (EmployeeCategoryInline,)
    actions = ("action_activate", "action_deactivate")

    readonly_fields = _StampedAdmin.readonly_fields + ("birthday_public_display_string", "coach_id_cache")

    fieldsets = (
        (_("Company & Status"), {
            "fields": ("active", "company"),
        }),
        (_("Identity"), {
            "fields": ("name", "user"),
        }),
        (_("Organization"), {
            "fields": ("department", "job", ("manager", "coach")),
        }),
        (_("Work Contact"), {
            "fields": ("work_contact", "work_email", ("work_phone", "mobile_phone")),
        }),
        (_("Location"), {
            "fields": ("work_location",),
        }),
        (_("Misc / Cache"), {
            "classes": ("collapse",),
            "fields": ("birthday_public_display_string", "coach_id_cache"),
        }),
        (_("Categories"), {
            "classes": ("collapse",),
            "fields": ("categories",),
        }),
        (_("Audit"), {
            "classes": ("collapse",),
            "fields": ("created_by", "created_at", "updated_by", "updated_at"),
        }),
    )

    @admin.display(description=_("Name"), ordering="name")
    def link_name(self, obj):
        url = reverse("admin:hr_employee_change", args=[obj.pk])
        return format_html('<a href="{}">{}</a>', url, obj.name)

# ========= Job =========

@admin.register(Job)
class JobAdmin(_StampedAdmin, _ActiveActionsMixin):
    list_display = (
        "link_name", "company", "department",
        "no_of_employee", "expected_employees", "active",
    )
    list_display_links = ("link_name",)
    list_filter = ("company", "department", "active")
    search_fields = ("name",)
    autocomplete_fields = ("department", "recruiter", "contract_type")
    ordering = ("company", "department", "name")
    list_per_page = 50
    list_select_related = ("company", "department", "recruiter", "contract_type")
    actions = ("action_activate", "action_deactivate")

    readonly_fields = _StampedAdmin.readonly_fields + ("no_of_employee", "expected_employees")

    fieldsets = (
        (_("General"), {
            "fields": ("active", "name", "sequence", "company", "department"),
        }),
        (_("Recruitment"), {
            "fields": ("recruiter", "contract_type", "no_of_recruitment"),
        }),
        (_("KPIs (computed)"), {
            "classes": ("collapse",),
            "fields": ("no_of_employee", "expected_employees"),
        }),
        (_("Description"), {
            "classes": ("collapse",),
            "fields": ("description", "requirements"),
        }),
        (_("Audit"), {
            "classes": ("collapse",),
            "fields": ("created_by", "created_at", "updated_by", "updated_at"),
        }),
    )

    @admin.display(description=_("Job"), ordering="name")
    def link_name(self, obj):
        url = reverse("admin:hr_job_change", args=[obj.pk])
        return format_html('<a href="{}">{}</a>', url, obj.name)

# ========= WorkLocation =========

@admin.register(WorkLocation)
class WorkLocationAdmin(_StampedAdmin, _ActiveActionsMixin):
    list_display = ("link_name", "company", "location_type", "address", "active")
    list_display_links = ("link_name",)
    list_filter = ("company", "location_type", "active")
    search_fields = ("name", "location_number", "address__display_name")
    autocomplete_fields = ("address",)
    ordering = ("company", "name")
    list_per_page = 50
    list_select_related = ("company", "address")
    actions = ("action_activate", "action_deactivate")

    fieldsets = (
        (_("General"), {
            "fields": ("active", "name", "company"),
        }),
        (_("Address & Type"), {
            "fields": ("location_type", "address", "location_number"),
        }),
        (_("Audit"), {
            "classes": ("collapse",),
            "fields": ("created_by", "created_at", "updated_by", "updated_at"),
        }),
    )

    @admin.display(description=_("Name"), ordering="name")
    def link_name(self, obj):
        url = reverse("admin:hr_worklocation_change", args=[obj.pk])
        return format_html('<a href="{}">{}</a>', url, obj.name)

# ========= EmployeeCategory =========

@admin.register(EmployeeCategory)
class EmployeeCategoryAdmin(_StampedAdmin):
    list_display = ("name", "color")
    search_fields = ("name",)
    ordering = ("name",)
    list_per_page = 50

# ========= ContractType =========

@admin.register(ContractType)
class ContractTypeAdmin(_StampedAdmin):
    list_display = ("name", "code", "sequence")
    search_fields = ("name", "code")
    ordering = ("sequence", "name")
    list_per_page = 50
