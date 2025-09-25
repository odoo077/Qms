from django.db import models
from .mixins import TimeStamped


class AssetType(TimeStamped):
    active = models.BooleanField(default=True)
    name = models.CharField(max_length=100, unique=True)
    default_warranty_months = models.PositiveIntegerField(default=12)

    class Meta:
        db_table = "emp_asset_type"
        ordering = ["name"]

    def __str__(self):
        return self.name
