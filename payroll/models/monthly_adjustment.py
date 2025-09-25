from django.db import models
from django.core.exceptions import ValidationError
from .mixins import TimeStamped


class MonthlyAdjustment(TimeStamped):
    """
    One-off monthly addition or deduction that applies to a specific payroll period.
    """
    employee = models.ForeignKey("hr.Employee", on_delete=models.CASCADE, related_name="monthly_adjustments")
    company = models.ForeignKey("base.Company", on_delete=models.PROTECT, related_name="monthly_adjustments")
    period = models.ForeignKey("payroll.PayrollPeriod", on_delete=models.CASCADE, related_name="adjustments")
    KIND = [("allowance", "Allowance"), ("deduction", "Deduction")]
    kind = models.CharField(max_length=10, choices=KIND)
    name = models.CharField(max_length=128)
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