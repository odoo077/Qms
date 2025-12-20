# payroll/models.py

from decimal import Decimal
from django.db import models
from django.core.exceptions import ValidationError
from django.db.models import Sum

from base.acl import ACLManager
from base.models import TimeStampedMixin

# ------------------------------------------------------------
# PayslipLine
# ------------------------------------------------------------
class PayslipLine(TimeStampedMixin):
    """
    خط قسيمة وفق Odoo: rule snapshot + الحساب النهائي.
    """
    payslip = models.ForeignKey("payroll.Payslip", on_delete=models.CASCADE, related_name="lines")
    code = models.CharField(max_length=50)  # من SalaryRule.code
    name = models.CharField(max_length=200)
    category = models.ForeignKey("payroll.SalaryRuleCategory", on_delete=models.PROTECT, related_name="payslip_lines")
    company = models.ForeignKey(
        "base.Company",
        on_delete=models.PROTECT,
        related_name="payslip_lines"
    )
    sequence = models.PositiveIntegerField(default=100)

    amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    quantity = models.DecimalField(max_digits=12, decimal_places=4, default=Decimal("1.0000"))
    rate = models.DecimalField(max_digits=7, decimal_places=4, default=Decimal("100.0000"))  # %
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        db_table = "payroll_payslip_line"
        ordering = ["sequence", "id"]
        indexes = [models.Index(fields=["payslip", "code", "category"])]
        constraints = [
            models.CheckConstraint(check=~models.Q(amount__lt=0), name="psl_amount_nonneg"),
            models.CheckConstraint(check=~models.Q(rate__lt=0), name="psl_rate_nonneg"),
            models.CheckConstraint(check=~models.Q(quantity__lt=0), name="psl_qty_nonneg"),
        ]

    def clean(self):
        super().clean()

        # If payslip not set yet, skip consistency check
        if not self.payslip_id:
            return

        # Auto-sync line company with payslip company (Odoo-like snapshot)
        if self.company_id is None:
            self.company = self.payslip.company

        if self.company_id != self.payslip.company_id:
            raise ValidationError({"company": "Company must match payslip company."})

    def __str__(self):
        return f"{self.code} - {self.total}"


# ------------------------------------------------------------
# PayrollPeriod
# ------------------------------------------------------------
class PayrollPeriod(TimeStampedMixin):
    """
    فترة الرواتب لشركة معيّنة (شهر/سنة + نطاق التاريخ).
    """
    company = models.ForeignKey("base.Company", on_delete=models.PROTECT, related_name="payroll_periods")

    date_from = models.DateField()
    date_to = models.DateField()

    month = models.PositiveSmallIntegerField()  # 1..12 (denormalized)
    year = models.PositiveSmallIntegerField()

    STATE = [("open", "Open"), ("closed", "Closed")]
    state = models.CharField(max_length=10, choices=STATE, default="open")

    objects = ACLManager()

    class Meta:
        db_table = "payroll_period"
        unique_together = [("company", "month", "year")]
        ordering = ["-year", "-month"]
        indexes = [models.Index(fields=["company", "year", "month", "state"])]
        constraints = [
            models.CheckConstraint(
                name="chk_payroll_period_dates",
                check=models.Q(date_from__lte=models.F("date_to")),
            ),
            models.CheckConstraint(
                name="chk_payroll_period_month_1_12",
                check=models.Q(month__gte=1, month__lte=12),
            ),
        ]

    def __str__(self):
        return f"{self.company} {self.year}-{self.month:02d} ({self.state})"


# ------------------------------------------------------------
# Payslip
# ------------------------------------------------------------
class Payslip(TimeStampedMixin):
    """
    القسيمة لموظف عن فترة معيّنة (header + snapshot totals).
    """
    employee = models.ForeignKey("hr.Employee", on_delete=models.PROTECT, related_name="payslips")
    company = models.ForeignKey("base.Company", on_delete=models.PROTECT, related_name="payslips")
    period = models.ForeignKey("payroll.PayrollPeriod", on_delete=models.PROTECT, related_name="payslips")

    # Snapshot
    department = models.ForeignKey("hr.Department", null=True, blank=True, on_delete=models.PROTECT,
                                   related_name="payslips")
    job = models.ForeignKey("hr.Job", null=True, blank=True, on_delete=models.PROTECT, related_name="payslips")

    # Totals
    basic = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    allowances = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    deductions = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    net = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    struct = models.ForeignKey("payroll.PayrollStructure", null=True, blank=True, on_delete=models.PROTECT,
                               related_name="payslips")
    gross_wage = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    net_wage = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    STATE = [("draft", "Draft"), ("validated", "Validated"), ("paid", "Paid"), ("cancel", "Cancelled")]
    state = models.CharField(max_length=10, choices=STATE, default="draft")

    note = models.CharField(max_length=255, blank=True)

    objects = ACLManager()

    class Meta:
        db_table = "payroll_payslip"
        # تفرد: قسيمة واحدة لكل (شركة، موظف، فترة)
        constraints = [
            models.UniqueConstraint(
                fields=["company", "employee", "period"],
                name="uniq_ps_co_emp_per",
            ),
        ]
        indexes = [
            # company + period + employee + state
            models.Index(
                fields=["company", "period", "employee", "state"],
                name="ps_c_p_e_s_idx",
            ),
            # company + period + department
            models.Index(
                fields=["company", "period", "department"],
                name="ps_c_p_dept_idx",
            ),
            # employee + period
            models.Index(
                fields=["employee", "period"],
                name="ps_emp_per_idx",
            ),
            # state فقط (لفلترة سريعة)
            models.Index(
                fields=["state"],
                name="ps_state_idx",
            ),
        ]

    def clean(self):
        super().clean()
        # company ↔ period.company
        if self.period_id and self.company_id and self.period.company_id != self.company_id:
            raise ValidationError({"company": "Company must match the payslip period company."})

        # company ↔ employee.company
        if self.employee_id and self.company_id and self.employee.company_id != self.company_id:
            raise ValidationError({"company": "Company must match the employee company."})

        # Snapshot fields (Odoo-like behavior)
        if self.employee_id:
            self.department = self.employee.department
            self.job = self.employee.job

    # ---- مجاميع السطور حسب الفئة (BASIC/ALW/DED) ----
    def _compute_totals(self):
        qs = self.lines.select_related("category")
        basic = qs.filter(category__code="BASIC").aggregate(t=Sum("total"))["t"] or Decimal("0.00")
        alw = qs.filter(category__code="ALW").aggregate(t=Sum("total"))["t"] or Decimal("0.00")
        ded = qs.filter(category__code="DED").aggregate(t=Sum("total"))["t"] or Decimal("0.00")
        return basic, alw, ded, (basic + alw - ded)

    def recompute(self, persist: bool = False):
        if self.state != "draft":
            raise ValidationError("Cannot recompute a non-draft payslip.")

        basic, allowances, deductions, net = self._compute_totals()
        self.basic = basic
        self.allowances = allowances
        self.deductions = deductions
        self.net = net
        self.gross_wage = basic + allowances
        self.net_wage = net
        if persist and self.pk:
            self.save(update_fields=["basic", "allowances", "deductions", "net", "gross_wage", "net_wage"])

    def __str__(self):
        return f"Payslip {self.employee} {self.period} [{self.state}]"



# ------------------------------------------------------------
# EmployeeSalary
# ------------------------------------------------------------
class EmployeeSalary(TimeStampedMixin):
    """
    الراتب الأساسي مع نافذة تاريخية — يحتفظ بالتاريخ عند التغيير.
    """
    employee = models.ForeignKey("hr.Employee", on_delete=models.CASCADE, related_name="salary_history", db_index=True)
    company = models.ForeignKey("base.Company", on_delete=models.PROTECT, related_name="salaries")

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date_start = models.DateField()
    date_end = models.DateField(null=True, blank=True)  # null = open

    note = models.CharField(max_length=255, blank=True)

    objects = ACLManager()

    class Meta:
        db_table = "payroll_employee_salary"
        ordering = ["-date_start"]
        indexes = [models.Index(fields=["employee", "company", "date_start", "date_end"])]

    def clean(self):
        if self.date_end and self.date_end < self.date_start:
            raise ValidationError("date_end must be >= date_start")
        if self.employee.company_id != self.company_id:
            raise ValidationError("Company must match the employee company.")

        # ❗ منع تداخل فترات الرواتب لنفس الموظف
        from django.db.models import Q
        qs = type(self)._base_manager.filter(
            employee=self.employee, company=self.company
        )
        if self.pk:
            qs = qs.exclude(pk=self.pk)

        # نعامل null كـ open-ended حتى تاريخ السجل الآخر
        start = self.date_start
        end = self.date_end

        overlaps = qs.filter(
            Q(date_end__isnull=True, date_start__lte=(end or start)) |
            Q(date_end__isnull=False, date_start__lte=(end or models.F("date_end")),
              date_end__gte=start)
        ).exists()

        if overlaps:
            raise ValidationError("Another salary period overlaps this range for the same employee.")

    def __str__(self):
        return f"{self.employee} - {self.amount} ({self.date_start} → {self.date_end or 'open'})"



class PayrollStructure(models.Model):
    """
    يماثل hr.payroll.structure
    """
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50)
    use_worked_day_lines = models.BooleanField(default=False)
    company = models.ForeignKey("base.Company", on_delete=models.PROTECT, related_name="pay_structures")

    objects = ACLManager()

    class Meta:
        db_table = "payroll_structure"
        unique_together = [("company", "code")]
        indexes = [models.Index(fields=["company", "code"])]

    def __str__(self):
        return self.name

# ===== Odoo-like: Category / Section =====
class SalaryRuleCategory(models.Model):
    """
    يماثل hr.salary.rule.category (لتجميع النتائج: BASIC, ALW, DED, NET...)
    """
    company = models.ForeignKey(
        "base.Company",
        on_delete=models.PROTECT,
        related_name="salary_rule_categories"
    )

    name = models.CharField(max_length=100)
    code = models.CharField(max_length=30)
    sequence = models.PositiveSmallIntegerField(default=100)

    class Meta:
        db_table = "payroll_rule_category"
        ordering = ["sequence"]
        unique_together = [("company", "code")]

    def __str__(self):
        return self.name

# ===== Odoo-like: Rule Parameter =====
class RuleParameter(models.Model):
    """
    يماثل hr.rule.parameter (قيم عامة قابلة للاستخدام داخل القواعد)
    """
    code = models.CharField(max_length=50)
    value = models.DecimalField(max_digits=12, decimal_places=4, default=Decimal("0.0000"))
    company = models.ForeignKey("base.Company", on_delete=models.PROTECT, related_name="pay_rule_params")

    class Meta:
        db_table = "payroll_rule_parameter"
        indexes = [models.Index(fields=["company", "code"])]
        unique_together = [("company", "code")]

    def __str__(self):
        return self.code

# ===== Odoo-like: Salary Rule =====
class SalaryRule(models.Model):
    """
    يماثل hr.salary.rule (شرط + حساب + تجميع)
    """
    struct = models.ForeignKey(PayrollStructure, on_delete=models.CASCADE, related_name="rules")
    code = models.CharField(max_length=50)  # مثال: BASIC, ALW_TRAN, DED_TAX, NET
    name = models.CharField(max_length=100)
    sequence = models.PositiveIntegerField(default=100)  # ترتيب التنفيذ
    category = models.ForeignKey(SalaryRuleCategory, on_delete=models.PROTECT, related_name="rules")

    CONDITION = [
        ("always", "Always"),
        ("python", "Python Expression"),
    ]
    condition_select = models.CharField(max_length=10, choices=CONDITION, default="always")
    condition_python = models.TextField(blank=True, default="result = True")  # يضبط متغير result

    # الحساب: Python expression (يضع total, amount, quantity, rate)
    amount_python = models.TextField(
        default="\n".join([
            "amount = BASIC",
            "quantity = 1",
            "rate = 100",
            "total = amount",
        ])
    )

    # خاصية إدخال على مستوى الموظف (Odoo property_input)
    input_usage_employee = models.BooleanField(default=False)

    # التحكم في منع التكرار
    unique_code_per_struct = models.BooleanField(default=True)

    class Meta:
        db_table = "payroll_salary_rule"
        ordering = ["sequence"]
        indexes = [
            models.Index(fields=["struct", "sequence"]),
            models.Index(fields=["struct", "code"]),
        ]
        unique_together = [("struct", "code")]  # ✅ لا تكرار لنفس الكود داخل نفس البنية

    def clean(self):
        super().clean()

        if self.unique_code_per_struct and type(self).objects.filter(
            struct=self.struct, code=self.code
        ).exclude(pk=self.pk).exists():
            raise ValidationError("Duplicate rule code within the same structure.")

        if self.struct_id and self.category_id:
            if self.struct.company_id != self.category.company_id:
                raise ValidationError("Rule category must belong to the same company as structure.")

# ===== Odoo-like: Payslip Input Type / Input (no attendance dependency) =====
class InputType(models.Model):
    """يماثل hr.payslip.input.type"""
    name = models.CharField(max_length=120)
    code = models.CharField(max_length=30)
    active = models.BooleanField(default=True)
    is_quantity = models.BooleanField(default=False)
    company = models.ForeignKey("base.Company", on_delete=models.PROTECT, related_name="pay_input_types")

    class Meta:
        db_table = "payroll_input_type"
        indexes = [models.Index(fields=["company", "code"])]
        unique_together = [("company", "code")]

    def __str__(self):
        return self.name

class PayslipInput(models.Model):
    """يماثل hr.payslip.input (يلتقط إدخالات يدوية/شهرية)"""

    company = models.ForeignKey(
        "base.Company",
        on_delete=models.PROTECT,
        related_name="payslip_inputs"
    )

    payslip = models.ForeignKey("payroll.Payslip", on_delete=models.CASCADE, related_name="inputs")
    input_type = models.ForeignKey(InputType, on_delete=models.PROTECT, related_name="payslip_inputs")
    name = models.CharField(max_length=200, blank=True, default="")
    sequence = models.PositiveIntegerField(default=10)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    @property
    def code(self):
        return self.input_type.code

    class Meta:
        db_table = "payroll_payslip_input"
        ordering = ["sequence", "id"]
        indexes = [
            models.Index(fields=["payslip", "input_type"]),
            models.Index(fields=["payslip", "sequence"]),
        ]

    def clean(self):
        super().clean()

        if not self.payslip_id:
            return

        # Auto-sync input company with payslip company
        if self.company_id is None:
            self.company = self.payslip.company

        if self.company_id != self.payslip.company_id:
            raise ValidationError({"company": "Company must match payslip company."})

    def __str__(self):
        return self.name or self.input_type.name
