from django.db import models
from .mixins import TimeStamped

class PayrollPeriod(TimeStamped):
    company = models.ForeignKey("base.Company", on_delete=models.PROTECT, related_name="payroll_periods")
    date_from = models.DateField()
    date_to = models.DateField()
    month = models.PositiveSmallIntegerField()  # 1..12, denormalized for convenience
    year = models.PositiveSmallIntegerField()
    STATE = [("open", "Open"), ("closed", "Closed")]
    state = models.CharField(max_length=10, choices=STATE, default="open")

    class Meta:
        db_table = "payroll_period"
        unique_together = [("company", "month", "year")]
        ordering = ["-year", "-month"]
        indexes = [models.Index(fields=["company", "year", "month", "state"])]

    def __str__(self):
        return f"{self.company} {self.year}-{self.month:02d} ({self.state})"