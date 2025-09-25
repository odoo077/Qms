from django.db import models
from .mixins import TimeStamped
from .assets_type import AssetType


class AssetModel(TimeStamped):
    active = models.BooleanField(default=True)
    type = models.ForeignKey(AssetType, on_delete=models.PROTECT, related_name="models")
    name = models.CharField(max_length=150)            # e.g., "ThinkPad X1 Carbon Gen 11"
    manufacturer = models.CharField(max_length=100, blank=True)
    sku = models.CharField(max_length=100, blank=True)
    specs = models.JSONField(default=dict, blank=True) # RAM/CPU/Size, etc.

    class Meta:
        db_table = "emp_asset_model"
        unique_together = [("type", "name")]
        ordering = ["type__name", "name"]

    def __str__(self):
        return f"{self.name} ({self.type.name})"
