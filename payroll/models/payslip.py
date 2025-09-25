from django.db import models
from decimal import Decimal
from .mixins import TimeStamped


class Payslip(TimeStamped):
    employee = models.ForeignKey("hr.Employee", on_delete=models.PROTECT, related_name="payslips")
    company = models.ForeignKey("base.Company", on_delete=models.PROTECT, related_name="payslips")
    period = models.ForeignKey("payroll.PayrollPeriod", on_delete=models.PROTECT, related_name="payslips")

    # SNAPSHOT FIELDS (recommended)
    department = models.ForeignKey("hr.Department", null=True, blank=True, on_delete=models.PROTECT, related_name="payslips")
    job = models.ForeignKey("hr.Job", null=True, blank=True, on_delete=models.PROTECT, related_name="payslips")

    basic = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    allowances = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    deductions = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    net = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    STATE = [("draft","Draft"),("confirmed","Confirmed"),("paid","Paid"),("cancelled","Cancelled")]
    state = models.CharField(max_length=10, choices=STATE, default="draft")

    note = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "payroll_payslip"
        unique_together = [("employee", "period")]
        indexes = [
            models.Index(fields=["company", "period", "employee", "state"]),
            models.Index(fields=["company", "period", "department"]),  # useful reports
        ]

    def _compute_totals(self):
        from .payslip_line import PayslipLine
        lines = PayslipLine.objects.filter(payslip=self)
        basic = sum((l.amount for l in lines.filter(kind="basic")), Decimal("0.00"))
        addi  = sum((l.amount for l in lines.filter(kind="allowance")), Decimal("0.00"))
        dedu  = sum((l.amount for l in lines.filter(kind="deduction")), Decimal("0.00"))
        return basic, addi, dedu, basic + addi - dedu

    def recompute(self, save=True):
        self.basic, self.allowances, self.deductions, self.net = self._compute_totals()
        if save:
            self.save(update_fields=["basic","allowances","deductions","net"])

    def save(self, *args, **kwargs):
        # Fill snapshot fields if missing
        if not self.department_id:
            self.department = self.employee.department
        if not self.job_id:
            self.job = self.employee.job
        # Company safety
        if self.employee.company_id != self.company_id:
            self.company_id = self.employee.company_id
        super().save(*args, **kwargs)
        self.recompute(save=True)

    def __str__(self):
        return f"Payslip {self.employee} {self.period} [{self.state}]"