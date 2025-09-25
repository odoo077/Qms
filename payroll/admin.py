# payroll/admin.py
from django.contrib import admin
from django.db.models import Sum
from .models import (
    PayrollPeriod, EmployeeSalary, RecurringComponent,
    MonthlyAdjustment, Payslip, PayslipLine
)
from . import services

# ----- Inlines -----
class PayslipLineInline(admin.TabularInline):
    model = PayslipLine
    extra = 0
    fields = ("name", "kind", "amount")
    readonly_fields = ()
    show_change_link = False

# ----- PayrollPeriod -----
@admin.register(PayrollPeriod)
class PayrollPeriodAdmin(admin.ModelAdmin):
    list_display = ("company", "year", "month", "date_from", "date_to", "state", "payslips_count", "total_net")
    list_filter = ("company", "year", "month", "state")
    search_fields = ("company__name",)
    actions = ["generate_payslips_for_company"]

    def payslips_count(self, obj):
        return obj.payslips.count()

    def total_net(self, obj):
        agg = obj.payslips.aggregate(n=Sum("net"))
        return agg["n"]

    @admin.action(description="Generate payslips for all company employees (overwrite existing)")
    def generate_payslips_for_company(self, request, queryset):
        from hr.models import Employee
        for period in queryset:
            emps = Employee.objects.filter(company=period.company, active=True)
            services.generate_payslips_for_period(period, emps, overwrite=True)

# ----- EmployeeSalary -----
@admin.register(EmployeeSalary)
class EmployeeSalaryAdmin(admin.ModelAdmin):
    list_display = ("employee", "company", "amount", "date_start", "date_end", "created_at", "updated_at")
    list_filter = ("company", "date_start", "date_end")
    search_fields = ("employee__name",)
    autocomplete_fields = ("employee", "company")

# ----- RecurringComponent -----
@admin.register(RecurringComponent)
class RecurringComponentAdmin(admin.ModelAdmin):
    list_display = ("employee", "company", "kind", "name", "amount", "date_start", "date_end", "active")
    list_filter = ("company", "kind", "active")
    search_fields = ("employee__name", "name")
    autocomplete_fields = ("employee", "company")

# ----- MonthlyAdjustment -----
@admin.register(MonthlyAdjustment)
class MonthlyAdjustmentAdmin(admin.ModelAdmin):
    list_display = ("period", "employee", "company", "kind", "name", "amount")
    list_filter = ("company", "period", "kind")
    search_fields = ("employee__name", "name")
    autocomplete_fields = ("employee", "company", "period")

# ----- Payslip -----
@admin.register(Payslip)
class PayslipAdmin(admin.ModelAdmin):
    list_display = ("employee", "company", "period", "department", "job", "basic", "allowances", "deductions", "net", "state")
    list_filter = ("company", "period", "state", "department", "job")
    search_fields = ("employee__name",)
    autocomplete_fields = ("employee", "company", "period", "department", "job")
    inlines = (PayslipLineInline,)
    actions = ["recompute_totals", "set_state_confirmed", "set_state_paid", "set_state_cancelled"]

    @admin.action(description="Recompute totals")
    def recompute_totals(self, request, queryset):
        for slip in queryset:
            slip.recompute(save=True)

    @admin.action(description="Mark as Confirmed")
    def set_state_confirmed(self, request, queryset):
        queryset.update(state="confirmed")

    @admin.action(description="Mark as Paid")
    def set_state_paid(self, request, queryset):
        queryset.update(state="paid")

    @admin.action(description="Cancel payslips")
    def set_state_cancelled(self, request, queryset):
        queryset.update(state="cancelled")