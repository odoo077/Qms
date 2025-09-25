from datetime import date
from dateutil.relativedelta import relativedelta
from django.db import models
from .mixins import TimeStamped
from .assets_model import AssetModel


class AssetItem(TimeStamped):
    STATUS = [
        ("in_stock", "In Stock"),
        ("assigned", "Assigned"),
        ("repair", "Repair"),
        ("lost", "Lost"),
        ("scrapped", "Scrapped"),
    ]
    active = models.BooleanField(default=True)
    company = models.ForeignKey("base.Company", on_delete=models.PROTECT, related_name="asset_items")

    model = models.ForeignKey(AssetModel, on_delete=models.PROTECT, related_name="items")
    asset_tag = models.CharField(max_length=64, unique=True)   # internal tag
    serial_no = models.CharField(max_length=128, blank=True, db_index=True)

    status = models.CharField(max_length=16, choices=STATUS, default="in_stock", db_index=True)

    purchase_date = models.DateField(null=True, blank=True)
    purchase_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    warranty_months = models.PositiveIntegerField(null=True, blank=True, help_text="Override type default")
    warranty_expiry = models.DateField(null=True, blank=True)  # stored compute

    location = models.CharField(max_length=128, blank=True)
    notes = models.TextField(blank=True)

    # Cached for fast filters: who currently holds it (stored compute)
    current_employee = models.ForeignKey("hr.Employee", null=True, blank=True,
                                         on_delete=models.SET_NULL, related_name="current_asset")

    class Meta:
        db_table = "emp_asset_item"
        indexes = [
            models.Index(fields=["company", "status"]),
            models.Index(fields=["model", "serial_no"]),
        ]
        ordering = ["model__type__name", "model__name", "asset_tag"]

    def __str__(self):
        return f"{self.asset_tag} – {self.model.name}"

    def _compute_warranty_expiry(self):
        months = self.warranty_months or (self.model.type.default_warranty_months if self.model_id else 0)
        self.warranty_expiry = (self.purchase_date + relativedelta(months=months)) if (self.purchase_date and months) else None

    def save(self, *args, **kwargs):
        # stored computes
        self._compute_warranty_expiry()
        super().save(*args, **kwargs)
