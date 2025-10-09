# assets/models/assets_item.py
from datetime import date
from dateutil.relativedelta import relativedelta
from django.db import models
from base.models.mixins import CompanyOwnedMixin, TimeStampedMixin, ActivableMixin, UserStampedMixin
from .assets_model import AssetModel

class AssetItem(CompanyOwnedMixin, TimeStampedMixin, ActivableMixin, UserStampedMixin):
    STATUS = [
        ("in_stock", "In Stock"),
        ("assigned", "Assigned"),
        ("repair", "Repair"),
        ("lost", "Lost"),
        ("scrapped", "Scrapped"),
    ]

    # CompanyOwnedMixin يضيف company + مدير scoped + فحص cross-company
    model = models.ForeignKey(AssetModel, on_delete=models.PROTECT, related_name="items")
    asset_tag = models.CharField(max_length=64)   # سنجعلها فريدة داخل الشركة
    serial_no = models.CharField(max_length=128, blank=True, db_index=True)

    status = models.CharField(max_length=16, choices=STATUS, default="in_stock", db_index=True)

    purchase_date = models.DateField(null=True, blank=True)
    purchase_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    warranty_months = models.PositiveIntegerField(null=True, blank=True, help_text="Override type default")
    warranty_expiry = models.DateField(null=True, blank=True)  # stored compute

    location = models.CharField(max_length=128, blank=True)
    notes = models.TextField(blank=True)

    current_employee = models.ForeignKey("hr.Employee", null=True, blank=True,
                                         on_delete=models.SET_NULL, related_name="current_assets")

    class Meta:
        db_table = "emp_asset_item"
        indexes = [
            models.Index(fields=["company", "status"]),
            models.Index(fields=["company", "serial_no"]),
            models.Index(fields=["company", "warranty_expiry"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["company", "asset_tag"], name="uniq_asset_tag_per_company"),
        ]
        ordering = ["model__type__name", "model__name", "asset_tag"]

        # ⬇️⬇️⬇️ أضِف هذا القسم
        permissions = [
            ("assign_item", "Can assign asset item"),
            ("return_item", "Can return asset item"),
            ("transfer_item", "Can transfer asset item"),
        ]

    def __str__(self):
        return f"{self.asset_tag} – {self.model.name}"

    def _compute_warranty_expiry(self):
        months = self.warranty_months or (self.model.type.default_warranty_months if self.model_id else 0)
        self.warranty_expiry = (
            self.purchase_date + relativedelta(months=months)
        ) if (self.purchase_date and months) else None

    def clean(self):
        super().clean()
        # فحص cross-company يأتي من CompanyOwnedMixin (model شركة تابعة؟)
        if self.model_id and self.model.type_id:  # لا حاجة للتحقق الإضافي الآن
            pass

    def save(self, *args, **kwargs):
        self._compute_warranty_expiry()
        return super().save(*args, **kwargs)
