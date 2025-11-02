# payroll/admin.py

from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .models import (
    PayrollPeriod,
    EmployeeSalary,
    Payslip,
    PayslipLine,
    PayrollStructure,
    SalaryRuleCategory,
    SalaryRule,
    RuleParameter, InputType, PayslipInput,
)
from . import services
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
    readonly_fields = ("code", "name", "category", "amount", "quantity", "rate", "total")
    can_delete = False


# ---------- EmployeeSalary ----------
@admin.register(EmployeeSalary)
class EmployeeSalaryAdmin(AppAdmin):
    list_display = ("employee", "company", "amount", "date_start", "date_end", "created_at", "updated_at")
    list_filter = ("company", "date_start", "date_end")
    search_fields = ("employee__name",)
    autocomplete_fields = ("employee", "company")


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

    @admin.action(description="Mark as Validated")
    def set_state_confirmed(self, request, queryset):
        queryset.update(state="validated")

    @admin.action(description="Mark as Paid")
    def set_state_paid(self, request, queryset):
        queryset.update(state="paid")

    @admin.action(description="Mark as Cancelled")
    def set_state_cancelled(self, request, queryset):
        queryset.update(state="cancel")

    @admin.action(description="Recompute lines (engine)")
    def action_recompute_lines(self, request, queryset):
        from . import services
        ok, errs = 0, 0
        for slip in queryset.select_related("struct"):
            try:
                services.recompute_lines(slip, persist=True)
                ok += 1
            except Exception as e:
                errs += 1
        self.message_user(request, f"✅ {ok} recomputed, ❗{errs} failed.")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        from . import services
        if (not change) or obj.lines.count() == 0:
            services.generate_payslip(obj.employee, obj.period, overwrite=True, note=obj.note or "")
            obj.refresh_from_db()

    actions = ["recompute_totals", "set_state_confirmed", "set_state_paid", "set_state_cancelled", "action_recompute_lines"]

    def change_view(self, request, object_id, form_url="", extra_context=None):
        # نحاول جلب السجل بأمان؛ إن لم يوجد نتجاوز إعادة الحساب
        obj = self.get_object(request, object_id)  # تعيد None إذا لم يُعثر عليه
        if obj is not None:
            try:
                obj.recompute(persist=True)
            except Exception:
                # تجنّب كسر صفحة الـ Admin إذا فشل الحساب
                pass
        return super().change_view(request, object_id, form_url, extra_context)


# ============================================================
# NEW: Odoo-like payroll definitions Admins
# ============================================================


@admin.register(PayrollStructure)
class PayrollStructureAdmin(AppAdmin):
    list_display = ("name", "code", "company", "use_worked_day_lines")
    list_filter = ("company", "use_worked_day_lines")
    search_fields = ("name", "code")
    autocomplete_fields = ("company",)

    @admin.action(description="Seed minimal rules (BASIC, ALW_TRAN, DED_TAX)")
    def action_seed_minimal_rules(self, request, queryset):
        ok, sk = 0, 0
        for struct in queryset:
            res = services.seed_minimal_rules(struct)
            ok += res["created"]
            sk += res["skipped"]
        self.message_user(request, f"✅ Rules created: {ok}, ↔️ skipped (already exist): {sk}")

    actions = getattr(locals(), "actions", []) + ["action_seed_minimal_rules"]

@admin.register(SalaryRuleCategory)
class SalaryRuleCategoryAdmin(AppAdmin):
    list_display = ("name", "code", "sequence")
    ordering = ("sequence", "id")
    search_fields = ("name", "code")


@admin.register(RuleParameter)
class RuleParameterAdmin(AppAdmin):
    list_display = ("code", "value", "company")
    list_filter = ("company",)
    search_fields = ("code",)
    autocomplete_fields = ("company",)


@admin.register(SalaryRule)
class SalaryRuleAdmin(AppAdmin):
    list_display = ("name", "code", "struct", "category", "sequence", "condition_select")
    list_filter = ("struct", "category", "condition_select")
    search_fields = ("name", "code")
    ordering = ("sequence", "id")
    autocomplete_fields = ("struct", "category")


@admin.register(InputType)
class InputTypeAdmin(AppAdmin):
    list_display = ("id", "name", "code", "company", "active", "is_quantity")
    list_filter = ("company", "active")
    search_fields = ("name", "code")
    autocomplete_fields = ("company",)


@admin.register(PayslipInput)
class PayslipInputAdmin(AppAdmin):
    list_display = ("id", "payslip", "input_type", "name", "amount", "sequence")
    list_select_related = ("payslip", "input_type")
    search_fields = ("name", "input_type__code", "payslip__id")
    autocomplete_fields = ("payslip", "input_type")
