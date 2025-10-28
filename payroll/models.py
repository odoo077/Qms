# -*- coding: utf-8 -*-
"""
Payroll models — بسيط وفعّال داخل نطاق HR:
- PayrollPeriod: فترة الرواتب
- EmployeeSalary: سجل الراتب الأساسي مع تاريخ النفاذ
- RecurringComponent: بدلات/استقطاعات ثابتة متكررة
- MonthlyAdjustment: تسوية شهرية لمرة واحدة
- Payslip / PayslipLine: القسيمة وخطوطها (لقطة Snapshot)
"""

from decimal import Decimal
from django.db import models
from django.core.exceptions import ValidationError

# مكسنات عامة من تطبيق base (نستخدم أساسًا الطوابع الزمنية)
from base.models import TimeStampedMixin


# ------------------------------------------------------------
# PayslipLine
# ------------------------------------------------------------
class PayslipLine(TimeStampedMixin):
    """
    Snapshot line. نخزّن الاسم/النوع/المبلغ وقت توليد القسيمة.
    kinds: 'basic', 'allowance', 'deduction'
    """
    payslip = models.ForeignKey("payroll.Payslip", on_delete=models.CASCADE, related_name="lines")
    name = models.CharField(max_length=128)

    KIND = [("basic", "Basic"), ("allowance", "Allowance"), ("deduction", "Deduction")]
    kind = models.CharField(max_length=10, choices=KIND)

    amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        db_table = "payroll_payslip_line"
        indexes = [models.Index(fields=["payslip", "kind"])]

    def __str__(self):
        sign = "+" if self.kind != "deduction" else "-"
        return f"{self.payslip}: {self.name} {sign}{self.amount}"


# ------------------------------------------------------------
# PayrollPeriod
# ------------------------------------------------------------
class PayrollPeriod(TimeStampedMixin):
    """
    فترة الرواتب لشركة معيّنة (شهر/سنة + نطاق التاريخ).
    """
    company = models.ForeignKey("base.Company", on_delete=models.PROTECT, related_name="payroll_periods")

    date_from = models.DateField()
    date_to   = models.DateField()

    month = models.PositiveSmallIntegerField()  # 1..12 (denormalized)
    year  = models.PositiveSmallIntegerField()

    STATE = [("open", "Open"), ("closed", "Closed")]
    state = models.CharField(max_length=10, choices=STATE, default="open")

    class Meta:
        db_table = "payroll_period"
        unique_together = [("company", "month", "year")]
        ordering = ["-year", "-month"]
        indexes = [models.Index(fields=["company", "year", "month", "state"])]

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
    company  = models.ForeignKey("base.Company", on_delete=models.PROTECT, related_name="payslips")
    period   = models.ForeignKey("payroll.PayrollPeriod", on_delete=models.PROTECT, related_name="payslips")

    # Snapshot: قسم/وظيفة وقت إنشاء القسيمة
    department = models.ForeignKey("hr.Department", null=True, blank=True, on_delete=models.PROTECT, related_name="payslips")
    job        = models.ForeignKey("hr.Job", null=True, blank=True, on_delete=models.PROTECT, related_name="payslips")

    # Totals (محسوبة)
    basic       = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    allowances  = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    deductions  = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    net         = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    STATE = [("draft", "Draft"), ("confirmed", "Confirmed"), ("paid", "Paid"), ("cancelled", "Cancelled")]
    state = models.CharField(max_length=10, choices=STATE, default="draft")

    note = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "payroll_payslip"
        unique_together = [("employee", "period")]
        indexes = [
            models.Index(fields=["company", "period", "employee", "state"]),
            models.Index(fields=["company", "period", "department"]),
        ]

    # ---- تجميع الأرقام من السطور ----
    def _compute_totals(self):
        lines = PayslipLine.objects.filter(payslip=self)
        basic = sum((l.amount for l in lines.filter(kind="basic")), Decimal("0.00"))
        addi  = sum((l.amount for l in lines.filter(kind="allowance")), Decimal("0.00"))
        dedu  = sum((l.amount for l in lines.filter(kind="deduction")), Decimal("0.00"))
        return basic, addi, dedu, basic + addi - dedu

    def recompute(self, persist=True):
        """
        نحسب المجاميع ثم —عند الحاجة— نحدّثها في قاعدة البيانات بدون استدعاء save()
        لتجنّب الاستدعاء الذاتي (recursion).
        """
        b, a, d, n = self._compute_totals()
        self.basic, self.allowances, self.deductions, self.net = b, a, d, n
        if persist and self.pk:
            type(self).objects.filter(pk=self.pk).update(
                basic=b, allowances=a, deductions=d, net=n
            )

    def save(self, *args, **kwargs):
        # سنابشوت القسم/الوظيفة + أمان الشركة
        if self.employee and not self.department_id:
            self.department = self.employee.department
        if self.employee and not self.job_id:
            self.job = self.employee.job
        if self.employee and self.employee.company_id != self.company_id:
            self.company_id = self.employee.company_id

        # حفظ الهيدر أولًا للحصول على PK
        super().save(*args, **kwargs)

        # بعد الحفظ: احسب وحدث المجاميع عبر UPDATE مباشر (بدون save() لتفادي recursion)
        self.recompute(persist=True)

    def __str__(self):
        return f"Payslip {self.employee} {self.period} [{self.state}]"


# ------------------------------------------------------------
# RecurringComponent
# ------------------------------------------------------------
class RecurringComponent(TimeStampedMixin):
    """
    بند متكرر (بدل/استقطاع) صالح ضمن نافذة تاريخية.
    """
    employee = models.ForeignKey("hr.Employee", on_delete=models.CASCADE, related_name="recurring_components")
    company  = models.ForeignKey("base.Company", on_delete=models.PROTECT, related_name="recurring_components")

    KIND = [("allowance", "Allowance"), ("deduction", "Deduction")]
    kind = models.CharField(max_length=10, choices=KIND)

    name   = models.CharField(max_length=128)
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    date_start = models.DateField()
    date_end   = models.DateField(null=True, blank=True)  # null = open

    active = models.BooleanField(default=True)

    class Meta:
        db_table = "payroll_recurring_component"
        ordering = ["kind", "name"]
        indexes = [models.Index(fields=["employee", "company", "kind", "date_start", "date_end", "active"])]

    def clean(self):
        if self.date_end and self.date_end < self.date_start:
            raise ValidationError("date_end must be >= date_start")
        if self.employee.company_id != self.company_id:
            raise ValidationError("Company must match the employee company.")

    def __str__(self):
        sign = "+" if self.kind == "allowance" else "-"
        return f"{self.employee}: {sign}{self.amount} {self.name}"


# ------------------------------------------------------------
# MonthlyAdjustment
# ------------------------------------------------------------
class MonthlyAdjustment(TimeStampedMixin):
    """
    تسوية شهرية (مرة واحدة) تخص فترة محدّدة.
    """
    employee = models.ForeignKey("hr.Employee", on_delete=models.CASCADE, related_name="monthly_adjustments")
    company  = models.ForeignKey("base.Company", on_delete=models.PROTECT, related_name="monthly_adjustments")
    period   = models.ForeignKey("payroll.PayrollPeriod", on_delete=models.CASCADE, related_name="adjustments")

    KIND = [("allowance", "Allowance"), ("deduction", "Deduction")]
    kind = models.CharField(max_length=10, choices=KIND)

    name   = models.CharField(max_length=128)
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = "payroll_monthly_adjustment"
        indexes = [models.Index(fields=["employee", "company", "period", "kind"])]

    def clean(self):
        if self.employee.company_id != self.company_id or self.period.company_id != self.company_id:
            raise ValidationError("Company must match for employee and period.")

    def __str__(self):
        sign = "+" if self.kind == "allowance" else "-"
        return f"{self.period}: {self.employee} {sign}{self.amount} {self.name}"


# ------------------------------------------------------------
# EmployeeSalary
# ------------------------------------------------------------
class EmployeeSalary(TimeStampedMixin):
    """
    الراتب الأساسي مع نافذة تاريخية — يحتفظ بالتاريخ عند التغيير.
    """
    employee = models.ForeignKey("hr.Employee", on_delete=models.CASCADE, related_name="salary_history", db_index=True)
    company  = models.ForeignKey("base.Company", on_delete=models.PROTECT, related_name="salaries")

    amount     = models.DecimalField(max_digits=12, decimal_places=2)
    date_start = models.DateField()
    date_end   = models.DateField(null=True, blank=True)  # null = open

    note = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "payroll_employee_salary"
        ordering = ["-date_start"]
        indexes = [models.Index(fields=["employee", "company", "date_start", "date_end"])]

    def clean(self):
        if self.date_end and self.date_end < self.date_start:
            raise ValidationError("date_end must be >= date_start")
        if self.employee.company_id != self.company_id:
            raise ValidationError("Company must match the employee company.")

    def __str__(self):
        return f"{self.employee} - {self.amount} ({self.date_start} → {self.date_end or 'open'})"
