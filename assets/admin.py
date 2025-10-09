# assets/admin.py
from django.contrib import admin, messages
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .models import (
    AssetType,
    AssetModel,
    AssetItem,
    EmployeeAsset,
)
from .services.assignment_service import AssignmentService


# ---------------------------
# List filters مخصصة
# ---------------------------
class WarrantySoonFilter(admin.SimpleListFilter):
    """عرض الأصول التي ينتهي ضمانها قريبًا (30 يومًا افتراضيًا)."""
    title = _("Warranty status")
    parameter_name = "warranty_soon"

    def lookups(self, request, model_admin):
        return (
            ("30", _("Expiring in ≤ 30 days")),
            ("60", _("Expiring in ≤ 60 days")),
            ("expired", _("Expired")),
        )

    def queryset(self, request, queryset):
        val = self.value()
        if not val:
            return queryset
        today = timezone.now().date()
        if val == "expired":
            return queryset.filter(warranty_expiry__isnull=False, warranty_expiry__lt=today)
        try:
            days = int(val)
        except Exception:
            return queryset
        bound = today + timezone.timedelta(days=days)
        return queryset.filter(warranty_expiry__isnull=False,
                               warranty_expiry__gte=today,
                               warranty_expiry__lte=bound)


class ActiveAssignmentFilter(admin.SimpleListFilter):
    """فلتر يُظهر العناصر المسلّمة حاليًا أو غير المسلّمة."""
    title = _("Assignment")
    parameter_name = "assigned"

    def lookups(self, request, model_admin):
        return (
            ("yes", _("Assigned")),
            ("no", _("Not assigned")),
        )

    def queryset(self, request, queryset):
        val = self.value()
        if val == "yes":
            return queryset.filter(current_employee__isnull=False)
        if val == "no":
            return queryset.filter(current_employee__isnull=True)
        return queryset


# ---------------------------
# Inlines
# ---------------------------
class EmployeeAssetInline(admin.TabularInline):
    """
    عرض تاريخ التسليمات على شاشة الأصل.
    القراءة فقط اختياريًا لتجنب التعديلات اللي تخالف قيود الخدمة.
    """
    model = EmployeeAsset
    fields = ("employee", "date_assigned", "due_back", "date_returned", "is_active", "is_overdue")
    readonly_fields = ("is_active", "is_overdue")
    extra = 0
    can_delete = False
    ordering = ("-date_assigned",)
    show_change_link = True

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("employee")


# ---------------------------
# Actions
# ---------------------------
@admin.action(description=_("Mark selected types as active"))
def make_active(modeladmin, request, queryset):
    updated = queryset.update(active=True)
    messages.success(request, _("%(n)d record(s) activated.") % {"n": updated})


@admin.action(description=_("Mark selected types as inactive"))
def make_inactive(modeladmin, request, queryset):
    updated = queryset.update(active=False)
    messages.success(request, _("%(n)d record(s) deactivated.") % {"n": updated})


@admin.action(description=_("Return selected active assignments (set return date = today)"))
def return_selected_assignments(modeladmin, request, queryset):
    today = timezone.now().date()
    count = 0
    with transaction.atomic():
        for rec in queryset.select_related("item"):
            if rec.is_active:
                AssignmentService.return_item(rec, date_returned=today, note="Admin bulk return")
                count += 1
    if count:
        messages.success(request, _("%(n)d assignment(s) returned.").format(n=count))
    else:
        messages.info(request, _("No active assignments were selected."))


# ---------------------------
# Admins
# ---------------------------
@admin.register(AssetType)
class AssetTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "default_warranty_months", "active")
    list_filter = ("active",)
    search_fields = ("name", "code")
    ordering = ("name",)
    actions = (make_active, make_inactive)


@admin.register(AssetModel)
class AssetModelAdmin(admin.ModelAdmin):
    list_display = ("name_display", "type", "manufacturer", "sku", "sequence", "active")
    list_filter = ("active", "type",)
    search_fields = ("name", "manufacturer", "sku", "type__name")
    ordering = ("type__name", "sequence", "name")
    actions = (make_active, make_inactive)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("type")

    @admin.display(description=_("Model"))
    def name_display(self, obj):
        # عرض محسّن: "Lenovo ThinkPad T14 (Laptop)"
        base = obj.name
        if obj.manufacturer:
            base = f"{obj.manufacturer} {base}"
        return f"{base} ({obj.type.name})"


@admin.register(AssetItem)
class AssetItemAdmin(admin.ModelAdmin):
    list_display = (
        "asset_tag", "company", "status", "model", "type_name",
        "serial_no", "current_employee", "purchase_date", "warranty_expiry", "active",
    )
    list_filter = (
        "active", "company", "status", "model__type",
        WarrantySoonFilter, ActiveAssignmentFilter,
    )
    search_fields = ("asset_tag", "serial_no", "model__name", "model__type__name",
                     "current_employee__name", "current_employee__work_email")
    ordering = ("company__name", "model__type__name", "model__name", "asset_tag")
    autocomplete_fields = ("model", "current_employee")
    inlines = (EmployeeAssetInline,)
    actions = (make_active, make_inactive)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("company", "model", "model__type", "current_employee")

    @admin.display(description=_("Type"))
    def type_name(self, obj):
        return getattr(obj.model.type, "name", None)


@admin.register(EmployeeAsset)
class EmployeeAssetAdmin(admin.ModelAdmin):
    list_display = (
        "item", "employee", "company",
        "date_assigned", "due_back", "date_returned",
        "is_active", "is_overdue",
    )
    list_filter = ("company", "is_active", "is_overdue")
    search_fields = (
        "item__asset_tag", "item__serial_no",
        "employee__name", "employee__work_email",
    )
    date_hierarchy = "date_assigned"
    ordering = ("-date_assigned",)
    autocomplete_fields = ("employee", "item")
    actions = (return_selected_assignments,)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("company", "employee", "item", "item__model", "item__model__type")
