from django.db import models
from django.core.exceptions import ValidationError
from .mixins import TimeStamped

class RecurringComponent(TimeStamped):
    """
    Fixed recurring additions/deductions: e.g., transport allowance, phone stipend,
    union fee, etc., with validity window.
    """
    employee = models.ForeignKey("hr.Employee", on_delete=models.CASCADE, related_name="recurring_components")
    company = models.ForeignKey("base.Company", on_delete=models.PROTECT, related_name="recurring_components")
    KIND = [("allowance", "Allowance"), ("deduction", "Deduction")]
    kind = models.CharField(max_length=10, choices=KIND)
    name = models.CharField(max_length=128)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date_start = models.DateField()
    date_end = models.DateField(null=True, blank=True)  # null = still valid

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