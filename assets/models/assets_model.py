# assets/models/assets_model.py
from django.db import models
from django.core.validators import MinValueValidator
from base.models.mixins import TimeStampedMixin, ActivableMixin
from .assets_type import AssetType


class AssetModel(TimeStampedMixin, ActivableMixin, models.Model):
    """
    طراز/موديل أصل مرتبط بالـ AssetType (مثلاً: ThinkPad T14 تحت نوع Laptop).
    - لا يحمل company (عبر-الشركات).
    - الحقول التقنية/التجارية اختيارية، و specs لتجميع مواصفات مرنة.
    """

    type = models.ForeignKey(
        AssetType, on_delete=models.PROTECT, related_name="models", db_index=True
    )

    # تعريف الموديل
    name = models.CharField(max_length=128, db_index=True)        # مثال: "ThinkPad T14 Gen 3"
    manufacturer = models.CharField(max_length=128, blank=True)    # مثال: "Lenovo"
    sku = models.CharField(
        max_length=128,
        blank=True,
        help_text="Manufacturer SKU / Part Number if applicable.",
    )

    # بيانات إضافية مرنة (JSON)
    specifications = models.JSONField(
        default=dict, blank=True,
        help_text="Arbitrary specs (e.g., {'cpu':'i7','ram':'16GB','ssd':'512GB'})."
    )

    # تحسينات للواجهات/العرض
    sequence = models.PositiveIntegerField(default=10, validators=[MinValueValidator(0)])
    color = models.CharField(max_length=16, blank=True)
    image = models.ImageField(upload_to="assets/models/", blank=True, null=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "emp_asset_model"
        ordering = ["type__name", "sequence", "name"]
        # قيود تساعد على تفادي التكرار المنطقي:
        constraints = [
            # نفس الاسم تحت نفس النوع لا يتكرر (إن لم تعتمد مصنّع/SKU)
            models.UniqueConstraint(
                fields=["type", "name"],
                name="uniq_asset_model_type_name",
            ),
            # إن توفّر manufacturer + sku معًا، فاجعلهما فريدين تحت نفس النوع
            models.UniqueConstraint(
                fields=["type", "manufacturer", "sku"],
                name="uniq_asset_model_type_mfr_sku",
                condition=models.Q(manufacturer__gt="", sku__gt=""),
            ),
        ]
        indexes = [
            models.Index(fields=["active"], name="asset_model_active_idx"),
            models.Index(fields=["type", "name"], name="asset_model_type_name_idx"),
        ]

    def __str__(self) -> str:
        base = self.name
        if self.manufacturer:
            base = f"{self.manufacturer} {base}"
        return base
