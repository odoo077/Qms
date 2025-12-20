# hr/admin.py
# ============================================================
# Django Admin (HR) — عرض غير مقيّد داخل لوحة الإدارة (Odoo-like)
#
# - نستخدم Mixin لإلغاء سكوب الشركات داخل الأدمن فقط.
# - جميع قوائم FK/M2M تعرض كل الخيارات (غير مقيّدة).
# - لا يؤثر هذا على منطق السكوب خارج الأدمن.
# ============================================================

from __future__ import annotations

from django.urls import reverse
from django.utils.html import format_html
from base.admin_mixins import AppAdmin, UnscopedAdminMixin
from . import models
from xfields.admin import XValueInline
from base.admin import ObjectACLInline
from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError

# ------------------------------------------------------------
# ContractType
# ------------------------------------------------------------
@admin.register(models.ContractType)
class ContractTypeAdmin(AppAdmin):
    list_display = ("name", "code", "sequence")
    search_fields = ("name", "code")
    ordering = ("sequence",)

    # لا تظهر في الفورم
    exclude = ("created_by", "updated_by", "created_at", "updated_at",)

    # إن فضلت عرضها للقراءة فقط بدل إخفائها:
    # readonly_fields = ("created_by", "updated_by", "created_at", "updated_at",)


# ------------------------------------------------------------
# Department
# ------------------------------------------------------------
@admin.register(models.Department)
class DepartmentAdmin(admin.ModelAdmin):
    """
    Odoo-like Admin behavior for Departments.

    Principles:
    - complete_name & parent_path are SYSTEM fields
    - Visible for transparency
    - Read-only to prevent manual corruption
    """

    list_display = (
        "complete_name",
        "company",
        "parent",
        "manager",
        "active",
    )

    list_filter = ("company", "active")
    search_fields = ("name", "complete_name")

    readonly_fields = (
        "complete_name",
        "parent_path",
    )

    fieldsets = (
        ("Department", {
            "fields": ("name", "company", "parent", "manager", "active"),
        }),
        ("Hierarchy (System)", {
            "fields": ("complete_name", "parent_path"),
        }),
        ("Notes", {
            "fields": ("note",),
        }),
    )


# ------------------------------------------------------------
# WorkLocation
# ------------------------------------------------------------
@admin.register(models.WorkLocation)
class WorkLocationAdmin(AppAdmin):
    list_display = ("name", "company", "location_type", "address", "active")
    list_filter = ("company", "location_type", "active")
    search_fields = ("name", "address__name", "address__email", "address__phone")
    list_select_related = ("company", "address")
    ordering = ("company", "name")

    autocomplete_fields = ("company", "address")


# ============================================================
# WorkShift / WorkShiftRule
# ============================================================

class WorkShiftForm(forms.ModelForm):
    """
    يتحقق مسبقًا من تفرد الاسم داخل الشركة فقط (company + name)،
    بما يتطابق مع قيد قاعدة البيانات uniq_ws_company_name.
    """
    class Meta:
        model = models.WorkShift
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()
        name = cleaned.get("name")
        company = cleaned.get("company")

        if name and company:
            qs = models.WorkShift._base_manager.filter(name=name, company=company)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError({"name": "A work shift with this name already exists in this company."})
        return cleaned

@admin.register(models.WorkShift)
class WorkShiftAdmin(UnscopedAdminMixin, admin.ModelAdmin):
    form = WorkShiftForm
    """
    شاشة الشفتات على مستوى الشركة فقط (لا قسم).
    """
    list_display = ("name", "company", "timezone", "hours_per_day", "active", "rules_count")
    list_filter  = ("company", "active", "timezone")
    search_fields = ("name", "code")
    ordering = ("company", "name")
    autocomplete_fields = ("company",)
    exclude = ("created_by", "updated_by")

    def rules_count(self, obj):
        return obj.rules.count()
    rules_count.short_description = "Rules"

class WorkShiftRuleInline(admin.TabularInline):
    """
    قواعد الشفت اليومية:
    - قاعدة واحدة لكل يوم (Mon..Sun).
    - دعم الشفت العابر لمنتصف الليل spans_next_day.
    - net_minutes للقراءة فقط لتسهيل المراجعة.
    """
    model = models.WorkShiftRule
    extra = 0
    fields = ("weekday", "start_time", "end_time", "spans_next_day", "break_minutes", "net_minutes")
    readonly_fields = ("net_minutes",)
    ordering = ("weekday", "start_time")

WorkShiftAdmin.inlines = [WorkShiftRuleInline]


# ============================================================
# EmployeeSchedule / EmployeeWeeklyOffPeriod (Inlines تحت Employee)
# ============================================================

class EmployeeScheduleInlineForm(forms.ModelForm):
    """
    يعرض weekly_off_mask كـ Checkboxes (Mon..Sun) في حقل وهمي 'weekly_off_days'.
    """
    weekly_off_days = forms.TypedMultipleChoiceField(
        choices=models.EmployeeSchedule.WEEKDAY_CHOICES,
        coerce=int,  # مهم: تأكد أن القيم int وليست strings
        widget=forms.CheckboxSelectMultiple,
        required=True,
        label="Weekly off days (Mon..Sun)",
        help_text="Select 1 day (6-day work) or 2 days (5-day work)."
    )

    class Meta:
        model  = models.EmployeeSchedule
        fields = ("active", "shift", "date_from", "date_to", "weekly_off_days")  # لا نظهر weekly_off_mask نفسه

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["weekly_off_days"].initial = models.EmployeeSchedule.weekday_list_from_mask(
                self.instance.weekly_off_mask
            )

    def clean(self):
        cleaned = super().clean()
        days = cleaned.get("weekly_off_days") or []
        # days بالفعل int بسبب coerce=int. لو أردت أماناً إضافياً:
        # days = [int(d) for d in days]

        # انسخ الاختيارات إلى الحقل الفعلي قبل model.clean()
        self.instance.weekly_off_mask = models.EmployeeSchedule.mask_from_weekday_list(days)

        # تحقق واجهة المستخدم (1 أو 2 يوم)
        if len(days) not in (1, 2):
            self.add_error("weekly_off_days", "Weekly off must be 1 day or 2 days.")
        return cleaned

    def save(self, commit=True):
        inst = super().save(commit=False)
        days = self.cleaned_data.get("weekly_off_days") or []
        inst.weekly_off_mask = models.EmployeeSchedule.mask_from_weekday_list(days)
        if commit:
            inst.save()
        return inst


class EmployeeScheduleInline(UnscopedAdminMixin, admin.TabularInline):
    """
    Inline تخص ربط الموظف بالشفت (بفترات) + اختيار العطلة الأسبوعية ضمن نفس السجل.
    """
    model = models.EmployeeSchedule
    form  = EmployeeScheduleInlineForm
    extra = 0
    fields = ("active", "shift", "date_from", "date_to", "weekly_off_days")
    ordering = ("-date_from",)
    # (اختياري) إخفاء حقول التتبع إن أردت
    exclude = ("created_by", "updated_by",)

    # نفس منطق حقن queryset للشفتات (لا تغيّر)
    def _compute_shift_queryset(self, request, obj=None):
        from hr.models import WorkShift, Employee
        qs = WorkShift._base_manager.all().filter(active=True)
        if obj and getattr(obj, "company_id", None):
            return qs.filter(company_id=obj.company_id)
        object_id = getattr(getattr(request, "resolver_match", None), "kwargs", {}).get("object_id")
        if object_id:
            emp = Employee._base_manager.only("id", "company_id").filter(pk=object_id).first()
            if emp and emp.company_id:
                return qs.filter(company_id=emp.company_id)
            return qs
        company_id = request.POST.get("company") or request.GET.get("company")
        if company_id:
            return qs.filter(company_id=company_id)
        return qs

    def get_formset(self, request, obj=None, **kwargs):
        ParentFormSet = super().get_formset(request, obj, **kwargs)
        allowed_shifts = self._compute_shift_queryset(request, obj=obj)

        class FixedFormSet(ParentFormSet):
            def __init__(self, *a, **kw):
                super().__init__(*a, **kw)
                for f in self.forms:
                    if "shift" in f.fields:
                        f.fields["shift"].queryset = allowed_shifts
                try:
                    if "shift" in self.empty_form.fields:
                        self.empty_form.fields["shift"].queryset = allowed_shifts
                except Exception:
                    pass

            def _construct_form(self, i, **kw):
                form = super()._construct_form(i, **kw)
                if "shift" in form.fields:
                    form.fields["shift"].queryset = allowed_shifts
                return form

            # NEW: تحقق عدم التداخل على مستوى الفورم-سِت (قبل الحفظ)
            def clean(self):
                super().clean()
                # اجمع السجلات التي لن تُحذف
                periods = []
                for form in self.forms:
                    if not hasattr(form, "cleaned_data"):
                        continue
                    cd = form.cleaned_data
                    if cd.get("DELETE"):
                        continue
                    if not cd.get("active", True):
                        continue
                    df = cd.get("date_from")
                    dt = cd.get("date_to")
                    if not df:
                        # يوجد تحقق آخر يجبر وجود date_from
                        continue
                    # اعتبر المفتوح حتى "لانهاية" لغرض المقارنة
                    from datetime import date
                    if dt is None:
                        dt_cmp = date(9999, 12, 31)
                    else:
                        dt_cmp = dt
                    periods.append((df, dt_cmp, form))

                # رتّب بالفترة من الأقدم للأحدث
                periods.sort(key=lambda t: t[0])

                # تحقق عدم التداخل: نهاية السابق < بداية اللاحق
                prev_end = None
                prev_form = None
                for df, dt, form in periods:
                    if prev_end is not None and df <= prev_end:
                        # خطأ على النموذج الحالي + السابق لتوضيح السبب
                        msg = "Employee already has an overlapping active schedule."
                        form.add_error(None, msg)
                        if prev_form:
                            prev_form.add_error(None, msg)
                    # حدّث المؤشر
                    if prev_end is None or dt > prev_end:
                        prev_end = dt
                        prev_form = form

        return FixedFormSet



# ============================================================
# EmployeeWeeklyOffPeriod (Checkboxes) – Inline ونموذج
# ============================================================

class EmployeeWeeklyOffPeriodForm(forms.ModelForm):
    """
    يعرض حقلاً افتراضيًا 'days' كـ Checkboxes (Mon..Sun) ويخزن داخليًا في days_mask (bitmask).
    """
    days = forms.TypedMultipleChoiceField(
        choices=models.EmployeeWeeklyOffPeriod.WEEKDAY_CHOICES,
        coerce=int,
        widget=forms.CheckboxSelectMultiple,
        required=True,
        label="Weekly off days (Mon..Sun)",
        help_text="Select one or more weekly off days."
    )

    class Meta:
        model = models.EmployeeWeeklyOffPeriod
        fields = ("active", "days", "date_from", "date_to")  # days بدل days_mask

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # اضبط القيمة الأولية اعتمادًا على الـ mask المخزون
        if self.instance and self.instance.pk:
            wd_list = models.EmployeeWeeklyOffPeriod.from_mask(self.instance.days_mask)
            self.fields["days"].initial = wd_list

    def clean(self):
        cleaned = super().clean()
        days = cleaned.get("days") or []
        self.instance.days_mask = models.EmployeeWeeklyOffPeriod.to_mask(days)
        if not days:
            self.add_error("days", "Select at least one weekly off day.")
        return cleaned

    def save(self, commit=True):
        inst = super().save(commit=False)
        days = self.cleaned_data.get("days") or []
        inst.days_mask = models.EmployeeWeeklyOffPeriod.to_mask(days)
        if commit:
            inst.save()
        return inst


class EmployeeWeeklyOffPeriodInline(UnscopedAdminMixin, admin.TabularInline):
    """
    إدارة العطلة الأسبوعية الثابتة كسجل واحد لكل فترة (مع Checkboxes للأيام).
    - يدعم فترات تاريخية (من/إلى).
    - يمنع التداخل على أيام متقاطعة وفق منطق clean() في الموديل.
    """
    model = models.EmployeeWeeklyOffPeriod
    form  = EmployeeWeeklyOffPeriodForm
    extra = 0
    fields = ("active", "days", "date_from", "date_to")
    ordering = ("-date_from",)


# -------------------------------
# Job
# -------------------------------
@admin.register(models.Job)
class JobAdmin(AppAdmin):
    list_display = (
        "name", "company", "department",
        "no_of_employee_display", "no_of_recruitment", "expected_employees_display",
        "active",
    )
    list_filter = ("company", "department", "active")
    search_fields = ("name", "department__name")
    list_select_related = ("company", "department")
    ordering = ("company", "department__complete_name", "name")
    autocomplete_fields = ("company", "department", "recruiter", "contract_type")

    # اعرض المُحتسبين في صفحة التفاصيل كحقول للقراءة فقط (الدوال، لا الحقول المخزّنة)
    readonly_fields = ("no_of_employee_display", "expected_employees_display")

    # ====== Helpers (unscoped + FK discovery) ======
    def _employee_unscoped_manager(self):
        """
        نأخذ مدير غير مقيّد لـ Employee كي لا يتأثر بـ Company Scope.
        - يفضّل all_objects إن كان معرّفًا، وإلا _base_manager.
        """
        Emp = models.Employee
        return getattr(Emp, "all_objects", Emp._base_manager)

    def _emp_fk_to_job(self) -> str:
        """
        نكتشف اسم حقل الـ FK من Employee → Job (مهما كان اسمه).
        """
        Emp = models.Employee
        for f in Emp._meta.get_fields():
            if getattr(f, "many_to_one", False) and getattr(f, "related_model", None) is models.Job:
                return f.name
        return "job"  # احتياط

    def _employees_qs_for_job(self, job_obj):
        """
        مصدر بيانات الموظفين لهذه الوظيفة عبر مدير غير مقيّد ثم نفلتر:
        - نفس الوظيفة
        - نفس الشركة (Odoo-like)
        - active=True إن وُجد الحقل
        """
        mgr = self._employee_unscoped_manager()
        fk = self._emp_fk_to_job()
        qs = mgr.filter(**{fk: job_obj})

        # فقط نفس الشركة
        if any(f.name == "company" for f in models.Employee._meta.get_fields()):
            qs = qs.filter(company=job_obj.company)

        # نشِط فقط
        if any(f.name == "active" for f in models.Employee._meta.get_fields()):
            qs = qs.filter(active=True)

        return qs

    # ====== Displays (استخدم هذه الأسماء في list_display و readonly_fields) ======
    @admin.display(description="No of employees", ordering=False)
    def no_of_employee_display(self, obj):
        return self._employees_qs_for_job(obj).count()

    @admin.display(description="Expected employees", ordering=False)
    def expected_employees_display(self, obj):
        return self.no_of_employee_display(obj) + (obj.no_of_recruitment or 0)



# ------------------------------------------------------------
# EmployeeCategory
# ------------------------------------------------------------
@admin.register(models.EmployeeCategory)
class EmployeeCategoryAdmin(AppAdmin):
    list_display = ("name", "color")
    search_fields = ("name",)
    ordering = ("name",)


# ------------------------------------------------------------
# Employee
# ------------------------------------------------------------

from django import forms

class EmployeeAdminForm(forms.ModelForm):
    class Meta:
        model = models.Employee
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()
        user = cleaned.get("user")
        company = cleaned.get("company")

        # (A) منع تكرار (user, company) — لديك هذا التحقق في الموديل أيضاً
        if user and company:
            qs = models.Employee.objects.filter(company=company, user=user)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError(
                    {"user": "This user already has an employee in this company."}
                )

        # (B) اتساق شركات المستخدم والموظف (مطابق لما في clean())
        if user and company:
            if getattr(user, "company_id", None) != getattr(company, "id", None):
                raise forms.ValidationError(
                    {"user": "User's main company must match the employee company."}
                )
            if hasattr(user, "companies") and not user.companies.filter(pk=company.id).exists():
                raise forms.ValidationError(
                    {"user": "Add this company to the user's allowed companies first."}
                )
        return cleaned



@admin.register(models.Employee)
class EmployeeAdmin(AppAdmin):
    """
    Employee Admin:
      - عرض شامل غير مقيّد داخل الأدمن.
      - تحسينات الأداء عبر select_related.
      - روابط سريعة إلى Partner/User عند الحاجة.
    """
    # أعمدة القائمة
    list_display = (
        "id",
        "name",
        "company",
        "department",
        "job",
        "manager",
        "user_link",
        "work_contact_link",
        "active",
    )
    list_filter = ("company", "department", "job", "active")
    search_fields = (
        "name",
        "user__email",
        "work_contact__name",
    )
    list_select_related = ("company", "department", "job", "manager", "user", "work_contact")
    ordering = ("company", "name")

    # اختيار العلاقات الثقيلة عبر autocomplete
    autocomplete_fields = (
        "company", "user", "department", "job", "manager", "coach",
        "work_location", "categories",
    )
    # مجموعات الحقول (تقسيم مرتب)
    fieldsets = (
        ("Core", {
            "fields": (
                "active",
                "company",
                "name",
                "user",
                "department",
                "job",
                "manager",
                "coach",
                "work_location",
                "categories",
            )
        }),
        ("Work Contact (Partner)", {
            "fields": (
                "work_contact_display",
            ),
            "description": "سيتم إنشاء/تعيين جهة اتصال العمل تلقائيًا عند الحفظ.",
        }),
        ("Private / Personal", {
            "fields": (
                "private_email",
                "private_phone",
                "birthday",
                "place_of_birth",
                "marital_status",
                "gender",
                "children",
            )
        }),
        ("IDs / Misc", {
            "fields": (
                "identification_id",
                "passport_id",
                "bank_account",
                "car",
                "barcode",
                "pin",
                "emergency_contact",
                "emergency_phone",
            )
        }),
    )

    form = EmployeeAdminForm

    readonly_fields = ("work_contact_display",)
    inlines = (EmployeeScheduleInline, EmployeeWeeklyOffPeriodInline, ObjectACLInline, XValueInline)

    # روابط سريعة
    def user_link(self, obj):
        if getattr(obj, "user_id", None):
            url = reverse("admin:base_user_change", args=[obj.user_id])
            return format_html('<a href="{}">User</a>', url)
        return "—"
    user_link.short_description = "User"

    def work_contact_link(self, obj):
        if getattr(obj, "work_contact_id", None):
            url = reverse("admin:base_partner_change", args=[obj.work_contact_id])
            return format_html('<a href="{}">Partner</a>', url)
        return "—"
    work_contact_link.short_description = "Work Contact"

    def work_contact_display(self, obj):
        if getattr(obj, "work_contact_id", None):
            url = reverse("admin:base_partner_change", args=[obj.work_contact_id])
            return format_html('<a href="{}">{} (open)</a>', url,
                               obj.work_contact.display_name or obj.work_contact.name)
        return "—"

    work_contact_display.short_description = "Work contact"


# ------------------------------------------------------------
# تحسينات عامة لعرض القيمة الفارغة
# ------------------------------------------------------------
admin.site.empty_value_display = "—"
