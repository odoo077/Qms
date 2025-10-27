# hr/admin.py
# ============================================================
# Django Admin (HR) — عرض غير مقيّد داخل لوحة الإدارة (Odoo-like)
#
# - نستخدم Mixin لإلغاء سكوب الشركات داخل الأدمن فقط.
# - جميع قوائم FK/M2M تعرض كل الخيارات (غير مقيّدة).
# - لا يؤثر هذا على منطق السكوب خارج الأدمن.
# ============================================================

from __future__ import annotations

from typing import Any
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from base.admin_mixins import AppAdmin
from . import models
from xfields.admin import XValueInline
from base.admin import ObjectACLInline


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
class DepartmentAdmin(AppAdmin):
    list_display = ("complete_name", "company", "parent", "manager", "active")
    list_filter = ("company", "active")
    search_fields = ("name", "complete_name", "manager__name", "parent__name")
    list_select_related = ("company", "parent", "manager")
    ordering = ("company", "complete_name")

    autocomplete_fields = ("company", "parent", "manager")


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
    inlines = (ObjectACLInline, XValueInline)


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
