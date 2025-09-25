# assets/admin.py
from django.contrib import admin
from django.utils import timezone
from .models import AssetType, AssetModel, AssetItem, EmployeeAsset


# ------------------------
# Inlines (on AssetItem)
# ------------------------

class EmployeeAssetInline(admin.TabularInline):
    model = EmployeeAsset
    extra = 0
    fields = (
        "employee", "date_assigned", "due_back", "date_returned",
        "is_active", "is_overdue", "handover_note", "return_note",
    )
    readonly_fields = ("is_active", "is_overdue")
    autocomplete_fields = ("employee",)
    show_change_link = True


# ------------------------
# AssetType
# ------------------------

@admin.register(AssetType)
class AssetTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "default_warranty_months", "active")
    list_filter = ("active",)
    search_fields = ("name",)
    ordering = ("name",)


# ------------------------
# AssetModel
# ------------------------

@admin.register(AssetModel)
class AssetModelAdmin(admin.ModelAdmin):
    list_display = ("name", "type", "manufacturer", "sku", "active")
    list_filter = ("type", "active")
    search_fields = ("name", "manufacturer", "sku")
    ordering = ("type__name", "name")
    autocomplete_fields = ("type",)


# ------------------------
# AssetItem
# ------------------------

@admin.register(AssetItem)
class AssetItemAdmin(admin.ModelAdmin):
    list_display = (
        "asset_tag", "model", "company", "status",
        "current_employee", "purchase_date", "warranty_expiry",
        "serial_no",
    )
    list_filter = (
        "status", "company", "model__type", "model",
        ("purchase_date", admin.DateFieldListFilter),
        ("warranty_expiry", admin.DateFieldListFilter),
    )
    search_fields = ("asset_tag", "serial_no", "model__name", "current_employee__name")
    ordering = ("model__type__name", "model__name", "asset_tag")
    readonly_fields = ("warranty_expiry", "current_employee")
    autocomplete_fields = ("company", "model", "current_employee")
    inlines = (EmployeeAssetInline,)
    actions = ("action_mark_in_stock", "action_mark_repair", "action_clear_holder")

    @admin.action(description="Mark selected items as In Stock")
    def action_mark_in_stock(self, request, queryset):
        queryset.update(status="in_stock", current_employee=None)

    @admin.action(description="Mark selected items as In Repair")
    def action_mark_repair(self, request, queryset):
        queryset.update(status="repair")

    @admin.action(description="Clear current holder (keep status)")
    def action_clear_holder(self, request, queryset):
        queryset.update(current_employee=None)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("model", "model__type", "company", "current_employee")


# ------------------------
# EmployeeAsset (assignments)
# ------------------------

@admin.register(EmployeeAsset)
class EmployeeAssetAdmin(admin.ModelAdmin):
    list_display = (
        "item", "employee", "company", "date_assigned",
        "due_back", "date_returned", "is_active", "is_overdue",
    )
    list_filter = (
        "is_active", "is_overdue", "item__status", "item__company",
        ("date_assigned", admin.DateFieldListFilter),
        ("due_back", admin.DateFieldListFilter),
        ("date_returned", admin.DateFieldListFilter),
    )
    search_fields = (
        "item__asset_tag", "item__serial_no", "item__model__name",
        "employee__name",
    )
    ordering = ("-date_assigned", "item__asset_tag")
    readonly_fields = ("is_active", "is_overdue")
    autocomplete_fields = ("employee", "item")

    # Convenience: show company via item (read-only)
    def company(self, obj):
        return obj.item.company if obj.item_id else None
    company.short_description = "Company"

    actions = ("action_mark_returned_today",)

    @admin.action(description="Mark returned (today)")
    def action_mark_returned_today(self, request, queryset):
        today = timezone.now().date()
        for a in queryset:
            if a.date_returned:
                continue
            a.date_returned = today
            a.save()

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("item", "item__model", "item__company", "employee")
