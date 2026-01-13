# assets/models.py
"""
تطبيق الأصول (assets) – بنية البيانات المتوافقة مع منطق Odoo
يتضمن دعم تعدد الشركات، التدرج الهرمي للفئات، وتعقب الإسنادات.
"""

from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from base.models import CompanyScopeManager

COMPANY_MODEL = "base.Company"
EMPLOYEE_MODEL = "hr.Employee"
DEPARTMENT_MODEL = "hr.Department"


# ============================================================
# Asset Category
# ============================================================

class AssetCategory(models.Model):
    """
    فئات الأصول – مشابهة لفئات Odoo (account.asset.category)
    """
    name = models.CharField(_("Name"), max_length=255)
    company = models.ForeignKey(
        COMPANY_MODEL, on_delete=models.CASCADE,
        related_name="asset_categories", verbose_name=_("Company"),
        db_index=True, null=True, blank=True
    )
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, related_name="children",
        verbose_name=_("Parent"), null=True, blank=True
    )
    parent_path = models.CharField(
        _("Parent path"), max_length=255, blank=True, default="", db_index=True
    )
    active = models.BooleanField(_("Active"), default=True)

    # --------- Human-friendly validation ----------
    def clean(self):
        """
        إظهار رسالة واضحة عندما يحاول المستخدم جعل الفئة أبًا لنفسها.
        """
        from django.core.exceptions import ValidationError

        if self.pk and self.parent_id == self.pk:
            raise ValidationError({
                "parent": _("Parent category cannot be the same as the category itself.")
            })

    objects = CompanyScopeManager()

    class Meta:
        db_table = "assets_category"
        indexes = [
            models.Index(fields=["company", "active"], name="as_cat_c_act_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "name"],
                name="as_cat_comp_name_uniq"
            ),
            models.CheckConstraint(
                name="as_cat_parent_not_self_chk",
                check=~models.Q(parent=models.F("pk")),
            ),
        ]
        ordering = ("company_id", "name")

    def __str__(self):
        return self.name


# ============================================================
# Asset
# ============================================================

class Asset(models.Model):
    """
    الأصول – يمثل الأصل الرئيسي كما في Odoo
    """

    class Status(models.TextChoices):
        AVAILABLE = "available", _("Available")
        ASSIGNED = "assigned", _("Assigned")
        MAINTENANCE = "maintenance", _("Maintenance")
        RETIRED = "retired", _("Retired")

    name = models.CharField(_("Name"), max_length=255)
    code = models.CharField(_("Code"), max_length=64, db_index=True)
    serial = models.CharField(_("Serial number"), max_length=128, blank=True, null=True)

    company = models.ForeignKey(
        COMPANY_MODEL, on_delete=models.CASCADE,
        related_name="assets", verbose_name=_("Company"), db_index=True
    )
    category = models.ForeignKey(
        AssetCategory, on_delete=models.SET_NULL,
        related_name="assets", verbose_name=_("Category"),
        null=True, blank=True
    )
    department = models.ForeignKey(
        DEPARTMENT_MODEL, on_delete=models.SET_NULL,
        related_name="assets", verbose_name=_("Department"),
        null=True, blank=True
    )
    holder = models.ForeignKey(
        EMPLOYEE_MODEL, on_delete=models.SET_NULL,
        related_name="holding_assets", verbose_name=_("Holder (employee)"),
        null=True, blank=True
    )

    status = models.CharField(
        _("Status"), max_length=16, choices=Status.choices,
        default=Status.AVAILABLE, db_index=True
    )

    purchase_date = models.DateField(_("Purchase date"), null=True, blank=True)
    purchase_value = models.DecimalField(
        _("Purchase value"), max_digits=12, decimal_places=2, null=True, blank=True
    )

    note = models.TextField(_("Notes"), blank=True, default="")
    active = models.BooleanField(_("Active"), default=True)

    parent = models.ForeignKey(
        "self", on_delete=models.SET_NULL,
        related_name="children", verbose_name=_("Parent Asset"),
        null=True, blank=True
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        related_name="created_assets", null=True, blank=True, verbose_name=_("Created by")
    )
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated at"), auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        related_name="updated_assets", null=True, blank=True, verbose_name=_("Updated by")
    )

    # ------------------------------------------------------------
    # Validations (human-friendly admin errors)
    # ------------------------------------------------------------
    def clean(self):
        from django.core.exceptions import ValidationError
        super().clean()

        errors = {}

        # (1) منطق الحالة ↔ الحامل
        if self.status == self.Status.ASSIGNED and not self.holder_id:
            errors["holder"] = "You must select a holder when status is ‘Assigned’."
        if self.status != self.Status.ASSIGNED and self.holder_id:
            errors["holder"] = "Holder can only be set when status is ‘Assigned’."

        # (2) اتساق الشركة عبر العلاقات
        if self.category_id and self.category.company_id != self.company_id:
            errors["category"] = "Category must belong to the same company as the asset."

        if self.department_id and self.department.company_id != self.company_id:
            errors["department"] = "Department must belong to the same company as the asset."

        if self.holder_id and self.holder.company_id != self.company_id:
            errors["holder"] = "Holder must belong to the same company as the asset."

        # (3) Parent: منع self-reference + اتساق الشركة
        if self.parent_id:
            if self.parent_id == self.pk:
                errors["parent"] = "Asset cannot be its own parent."
            elif self.parent.company_id != self.company_id:
                errors["parent"] = "Parent asset must belong to the same company as the asset."

        if errors:
            raise ValidationError(errors)

    objects = CompanyScopeManager()

    class Meta:
        db_table = "assets_asset"
        indexes = [
            models.Index(fields=["company", "active"], name="as_ast_c_act_idx"),
            models.Index(fields=["company", "status"], name="as_ast_c_st_idx"),
            models.Index(fields=["company", "holder"], name="as_ast_c_holder_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"],
                name="as_ast_comp_code_uniq"
            ),
            models.UniqueConstraint(
                fields=["company", "serial"],
                name="as_ast_comp_serial_uniq",
                condition=models.Q(serial__isnull=False) & ~models.Q(serial=""),
            ),
            models.CheckConstraint(
                name="as_ast_status_holder_chk",
                check=models.Q(status="assigned", holder__isnull=False)
                      | ~models.Q(status="assigned"),
            ),
        ]
        ordering = ("company_id", "name", "code")

    def __str__(self):
        return f"{self.code} - {self.name}"


# ============================================================
# Asset Assignment
# ============================================================

class AssetAssignment(models.Model):
    """
    سجل إسناد الأصول للموظفين (تاريخي)
    """

    asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        related_name="assignments",
        verbose_name=_("Asset"),
    )
    employee = models.ForeignKey(
        EMPLOYEE_MODEL,
        on_delete=models.CASCADE,
        related_name="asset_assignments",
        verbose_name=_("Employee"),
    )
    company = models.ForeignKey(
        COMPANY_MODEL,
        on_delete=models.CASCADE,
        related_name="asset_assignments",
        verbose_name=_("Company"),
    )

    date_from = models.DateField(_("From"), null=True, blank=True)
    date_to = models.DateField(_("To"), null=True, blank=True)
    note = models.CharField(_("Note"), max_length=255, blank=True, default="")

    # ------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------
    def clean(self):
        from django.core.exceptions import ValidationError
        super().clean()

        errors = {}
        asset = self.asset

        if not asset:
            raise ValidationError({"asset": "Asset is required."})

        # (1) منع أكثر من إسناد مفتوح
        open_qs = type(self).objects.filter(asset=asset, date_to__isnull=True)
        if self.pk:
            open_qs = open_qs.exclude(pk=self.pk)

        if open_qs.exists() and self.date_to is None:
            errors["asset"] = "There is already an open assignment for this asset."

        # (2) تحقق التواريخ
        if self.date_from and self.date_to and self.date_to < self.date_from:
            errors["date_to"] = "End date must be greater than or equal to start date."

        # (3) اتساق الشركة
        if self.employee.company_id != asset.company_id:
            errors["employee"] = "Employee must belong to the same company as the asset."

        # (4) الأصل فعّال
        if not asset.active:
            errors["asset"] = "Cannot assign an inactive asset."

        # (5) الإسناد المفتوح فقط عند Available
        if self.date_to is None and asset.status != asset.Status.AVAILABLE:
            errors["asset"] = (
                f"Cannot assign asset while status is '{asset.status}'. "
                "Asset must be in 'Available' status."
            )

        if errors:
            raise ValidationError(errors)

    objects = CompanyScopeManager()

    class Meta:
        db_table = "assets_assignment"
        ordering = ("-id",)
        indexes = [
            models.Index(fields=["company"], name="as_asg_company_idx"),
            models.Index(fields=["asset", "employee"], name="as_asg_ast_emp_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                name="as_asg_dates_chk",
                check=(
                    models.Q(date_to__isnull=True)
                    | models.Q(date_from__isnull=True)
                    | models.Q(date_to__gte=models.F("date_from"))
                ),
            ),
            models.UniqueConstraint(
                fields=["asset"],
                condition=models.Q(date_to__isnull=True),
                name="as_asg_one_open_per_asset",
            ),
        ]

    def __str__(self):
        return f"{self.asset} → {self.employee}"
