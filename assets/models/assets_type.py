# assets/models/assets_type.py
from django.db import models
from base.models.mixins import TimeStampedMixin, ActivableMixin


class AssetType(TimeStampedMixin, ActivableMixin, models.Model):
    """
    نوع أصل عام (Laptop, Phone, Monitor, Access Card, ...).
    - كيان عبر الشركات (لا يحمل company) ليسهل إعادة الاستخدام.
    - يستخدم ActivableMixin لتفعيل/تعطيل النوع دون حذفه.
    """

    name = models.CharField(max_length=128, unique=True, db_index=True)
    code = models.SlugField(
        max_length=64,
        unique=True,
        help_text="Unique code/slug for referencing in integrations (e.g., 'laptop', 'phone').",
    )
    default_warranty_months = models.PositiveIntegerField(
        default=0,
        help_text="Default warranty for items of this type (months). Can be overridden on the item.",
    )
    description = models.TextField(blank=True)

    icon = models.CharField(
        max_length=64,
        blank=True,
        help_text="Optional icon name (for UI only).",
    )

    class Meta:
        db_table = "emp_asset_type"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["active"], name="asset_type_active_idx"),
            models.Index(fields=["name"], name="asset_type_name_idx"),
        ]

    def __str__(self) -> str:
        return self.name
