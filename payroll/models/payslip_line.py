from django.db import models
from decimal import Decimal
from .mixins import TimeStamped


class PayslipLine(TimeStamped):
    """
    Snapshot line. We store component name/type/amount as of generation time.
    Kinds: 'basic', 'allowance', 'deduction'.
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