from django.db import models
from base.models.mixins import TimeStamped, UserStamped

# لتجميع متقاطع (فرق/مجموعات غير هرمية)
class EmployeeCategory(TimeStamped, UserStamped, models.Model):
    """Odoo-like hr.employee.category (tags)."""
    name = models.CharField(max_length=128, unique=True)
    color = models.PositiveSmallIntegerField(default=1)

    class Meta:
        db_table = "hr_employee_category"

    def __str__(self):
        return self.name
