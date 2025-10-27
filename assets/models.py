# -*- coding: utf-8 -*-
"""
تطبيق الأصول (assets) – بنية البيانات المتوافقة مع منطق Odoo
يتضمن دعم تعدد الشركات، التدرج الهرمي للفئات، وتعقب الإسنادات.
"""

from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from base.acl import AccessControlledMixin


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
    parent_path = models.CharField(_("Parent path"), max_length=255, blank=True, default="", db_index=True)
    active = models.BooleanField(_("Active"), default=True)

    # --------- Human-friendly validation ----------
    def clean(self):
        """
        إظهار رسالة واضحة عندما يحاول المستخدم جعل الفئة أبًا لنفسها.
        """
        from django.core.exceptions import ValidationError

        # عند التعديل فقط يكون self.pk معروفًا؛ تأكد أن الأب ليس هو نفس السجل
        if self.pk and self.parent_id == self.pk:
            raise ValidationError({
                "parent": _("Parent category cannot be the same as the category itself.")
            })

    class Meta:
        db_table = "assets_category"
        indexes = [
            models.Index(fields=["company", "active"], name="as_cat_c_act_idx"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["company", "name"], name="as_cat_comp_name_uniq"),
            # نُبقي قيد قاعدة البيانات للحماية الصلبة
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

class Asset(AccessControlledMixin, models.Model):
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
    purchase_value = models.DecimalField(_("Purchase value"), max_digits=12, decimal_places=2, null=True, blank=True)
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
        """
        عرض رسالة واضحة للمستخدم الإداري بدل رسالة قاعدة البيانات
        عندما تكون الحالة 'Assigned' بدون حامل، أو العكس.
        """
        from django.core.exceptions import ValidationError

        # حالة "Assigned" تتطلب وجود حامل
        if self.status == self.Status.ASSIGNED and not self.holder_id:
            raise ValidationError({
                "holder": "You must select a holder when status is ‘Assigned’."
            })

        # إن كانت الحالة ليست "Assigned" فلا يجوز وجود حامل
        if self.status != self.Status.ASSIGNED and self.holder_id:
            raise ValidationError({
                "holder": "Holder can only be set when status is ‘Assigned’."
            })

        # شركات الحقول المرتبطة يجب أن تطابق شركة الأصل (رسالة ودية)
        if self.category_id and getattr(self.category, "company_id", None) and self.category.company_id != self.company_id:
            raise ValidationError({"category": "Category must belong to the same company as the asset."})

        if self.department_id and getattr(self.department, "company_id", None) and self.department.company_id != self.company_id:
            raise ValidationError({"department": "Department must belong to the same company as the asset."})

        if self.holder_id and getattr(self.holder, "company_id", None) and self.holder.company_id != self.company_id:
            raise ValidationError({"holder": "Holder must belong to the same company as the asset."})



    class Meta:
        db_table = "assets_asset"
        indexes = [
            models.Index(fields=["company", "active"], name="as_ast_c_act_idx"),
            models.Index(fields=["company", "status"], name="as_ast_c_st_idx"),
            models.Index(fields=["company", "holder"], name="as_ast_c_holder_idx"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["company", "code"], name="as_ast_comp_code_uniq"),
            models.UniqueConstraint(
                fields=["company", "serial"],
                name="as_ast_comp_serial_uniq",
                condition=models.Q(serial__isnull=False),
            ),
            # ✅ الحالة Assigned يجب أن يكون لها حامل، أو أي حالة أخرى بدون حامل
            models.CheckConstraint(
                name="as_ast_status_holder_chk",
                check=models.Q(status="assigned", holder__isnull=False) | ~models.Q(status="assigned"),
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
    سجل الإسناد (تاريخ تسليم الأصول لموظفين)
    - يعكس سجل تغيّر المالك كما في Odoo (ir.attachment / asset.log)
    """
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="assignments", verbose_name=_("Asset"))
    employee = models.ForeignKey(
        EMPLOYEE_MODEL, on_delete=models.CASCADE,
        related_name="asset_assignments", verbose_name=_("Employee")
    )
    company = models.ForeignKey(
        COMPANY_MODEL, on_delete=models.CASCADE,
        related_name="asset_assignments", verbose_name=_("Company")
    )
    date_from = models.DateField(_("From"), null=True, blank=True)
    date_to = models.DateField(_("To"), null=True, blank=True)
    note = models.CharField(_("Note"), max_length=255, blank=True, default="")
    active = models.BooleanField(_("Active"), default=True)

    def clean(self):
        from django.core.exceptions import ValidationError
        # تأكد أنه لا توجد عهدة مفتوحة أخرى لهذا الأصل
        open_exists = type(self).objects.filter(asset=self.asset, date_to__isnull=True, active=True)
        if self.pk:
            open_exists = open_exists.exclude(pk=self.pk)
        if open_exists.exists() and (self.date_to is None):
            raise ValidationError({"asset": "There is already an open assignment for this asset."})

        # تحقق ودّي للتواريخ
        if self.date_from and self.date_to and self.date_to < self.date_from:
            raise ValidationError({"date_to": "End date must be greater than or equal to start date."})


    class Meta:
        db_table = "assets_assignment"
        indexes = [
            models.Index(fields=["company", "active"], name="as_asg_c_act_idx"),
            models.Index(fields=["asset", "employee"], name="as_asg_ast_emp_idx"),
        ]
        constraints = [
            # ✅ تاريخ الانتهاء إن وُجد يجب أن يكون ≥ تاريخ البدء (لا يوجد join هنا)
            models.CheckConstraint(
                name="as_asg_dates_chk",
                check=models.Q(date_to__isnull=True) |
                      models.Q(date_from__isnull=True) |
                      models.Q(date_to__gte=models.F("date_from")),
            ),
            # ✅ يسمح بإسنادات متعددة عبر الزمن، لكن يمنع أكثر من إسناد مفتوح لنفس الأصل
            models.UniqueConstraint(
                fields=["asset"],
                name="as_asg_one_open_per_asset",
                condition=models.Q(date_to__isnull=True),
            ),
        ]
        ordering = ("-id",)

    def __str__(self):
        return f"{self.asset} -> {self.employee}"
