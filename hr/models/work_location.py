from django.db import models
from . import TimeStamped, UserStamped


class WorkLocation(TimeStamped, UserStamped, models.Model):
    """
    Odoo hr.work.location: active, name, company, type, address ref, location number.
    """
    active = models.BooleanField(default=True)
    name = models.CharField(max_length=255)
    company = models.ForeignKey("base.Company", on_delete=models.PROTECT)
    LOCATION_TYPE = [("home", "Home"), ("office", "Office"), ("other", "Other")]
    location_type = models.CharField(max_length=10, choices=LOCATION_TYPE, default="office")
    address = models.ForeignKey("base.Partner", on_delete=models.PROTECT)
    location_number = models.CharField(max_length=64, blank=True)

    class Meta:
        db_table = "hr_work_location"

    def __str__(self):
        return self.name
