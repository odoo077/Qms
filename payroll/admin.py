# -*- coding: utf-8 -*-
"""
لوحة الإدارة — ترث من AppAdmin لاستثناء القيود وعرض كل السجلات (Unscoped).
"""

from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .models import (
    PayrollPeriod,
    EmployeeSalary,
    RecurringComponent,
    MonthlyAdjustment,
    Payslip,
    PayslipLine,
)
from base.admin_mixins import AppAdmin, _unscoped_manager


# ============================================================
# PayrollPeriod
# ============================================================
@admin.register(PayrollPeriod)
class PayrollPeriodAdmin(AppAdmin):
    """
    شاشة إدارة فترات الرواتب
    """
    list_display = ("__str__", "company", "date_from", "date_to", "state", "active_employees_count")
    list_filter = ("company", "state", "year", "month")
    search_fields = ("company__name",)
    ordering = ("-year", "-month")

    @admin.display(description=_("Active employees"))
    def active_employees_count(self, obj):
        from django.apps import apps
        Emp = apps.get_model("hr", "Employee")
        qs = _unscoped_manager(Emp).all().filter(company_id=obj.company_id)
        if any(f.name == "active" for f in Emp._meta.get_fields()):
            qs = qs.filter(active=True)
        return qs.count()

    # ===== Actions =====
    @admin.action(description="Generate payslips for all active employees (overwrite existing)")
    def action_generate_all_payslips(self, request, queryset):
        from django.apps import apps
        from base.admin_mixins import _unscoped_manager
        from . import services
        Emp = apps.get_model("hr", "Employee")

        total = 0
        for period in queryset:
            emps = _unscoped_manager(Emp).all().filter(company_id=period.company_id)
            if any(f.name == "active" for f in Emp._meta.get_fields()):
                emps = emps.filter(active=True)
            services.generate_payslips_for_period(period, emps, overwrite=True)
            total += emps.count()
        self.message_user(request, f"✅ {total} payslip(s) generated successfully.")

    @admin.action(description="Close selected periods")
    def action_close_periods(self, request, queryset):
        queryset.update(state="closed")
        self.message_user(request, f"✅ {queryset.count()} period(s) closed successfully.")

    actions = ["action_generate_all_payslips", "action_close_periods"]

    def get_queryset(self, request):
        # عرض كل الفترات (حتى المغلقة) مع بيانات الشركة
        return super().get_queryset(request).select_related("company")


# ------------------------------------------------------------
# PayslipLine Inline (تابعة لكل Payslip)
# ------------------------------------------------------------
class PayslipLineInline(admin.TabularInline):
    model = PayslipLine
    extra = 0
    readonly_fields = ("kind", "amount", "name")
    can_delete = False

# ---------- EmployeeSalary ----------
@admin.register(EmployeeSalary)
class EmployeeSalaryAdmin(AppAdmin):
    list_display = ("employee", "company", "amount", "date_start", "date_end", "created_at", "updated_at")
    list_filter = ("company", "date_start", "date_end")
    search_fields = ("employee__name",)
    autocomplete_fields = ("employee", "company")


# ---------- RecurringComponent ----------
@admin.register(RecurringComponent)
class RecurringComponentAdmin(AppAdmin):
    list_display = ("employee", "company", "kind", "name", "amount", "date_start", "date_end", "active")
    list_filter = ("company", "kind", "active")
    search_fields = ("employee__name", "name")
    autocomplete_fields = ("employee", "company")


# ---------- MonthlyAdjustment ----------
@admin.register(MonthlyAdjustment)
class MonthlyAdjustmentAdmin(AppAdmin):
    list_display = ("period", "employee", "company", "kind", "name", "amount")
    list_filter = ("company", "period", "kind")
    search_fields = ("employee__name", "name")
    autocomplete_fields = ("employee", "company", "period")


# ---------- Payslip ----------
@admin.register(Payslip)
class PayslipAdmin(AppAdmin):
    list_display = ("employee", "company", "period", "department", "job",
                    "basic", "allowances", "deductions", "net", "state")
    list_filter = ("company", "period", "state", "department", "job")
    search_fields = ("employee__name",)
    autocomplete_fields = ("employee", "company", "period", "department", "job")
    inlines = (PayslipLineInline,)

    # المجاميع للقراءة فقط (تُحتسب تلقائيًا)
    readonly_fields = ("basic", "allowances", "deductions", "net")

    @admin.action(description="Recompute totals")
    def recompute_totals(self, request, queryset):
        for slip in queryset:
            slip.recompute(persist=True)

    @admin.action(description="Mark as Confirmed")
    def set_state_confirmed(self, request, queryset):
        queryset.update(state="confirmed")

    @admin.action(description="Mark as Paid")
    def set_state_paid(self, request, queryset):
        queryset.update(state="paid")

    @admin.action(description="Cancel payslips")
    def set_state_cancelled(self, request, queryset):
        queryset.update(state="cancelled")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        from . import services
        if (not change) or obj.lines.count() == 0:
            services.generate_payslip(obj.employee, obj.period, overwrite=True, note=obj.note or "")

    actions = ["recompute_totals", "set_state_confirmed", "set_state_paid", "set_state_cancelled"]
