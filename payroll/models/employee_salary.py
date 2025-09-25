from django.db import models
from django.core.exceptions import ValidationError
from .mixins import TimeStamped

class EmployeeSalary(TimeStamped):
    """
    Base (fixed) salary with validity window – keeps history when you change salary.
    """
    employee = models.ForeignKey("hr.Employee", on_delete=models.CASCADE, related_name="salary_history", db_index=True)
    company = models.ForeignKey("base.Company", on_delete=models.PROTECT, related_name="salaries")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date_start = models.DateField()
    date_end = models.DateField(null=True, blank=True)  # null = still valid

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