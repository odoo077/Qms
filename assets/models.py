from dateutil.relativedelta import relativedelta
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.core.exceptions import ValidationError
from base.models import CompanyOwnedMixin, ActivableMixin, TimeStampedMixin, UserStampedMixin
from django.utils import timezone

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
class EmployeeAsset(CompanyOwnedMixin, TimeStampedMixin, UserStampedMixin):
    """
    Assignment record (history). Exactly one active assignment per item.
    Denormalized company = item.company (يحسّن الفلترة/الفهارس).
    """
    employee = models.ForeignKey("hr.Employee", on_delete=models.CASCADE,
                                 related_name="asset_assignments", db_index=True)
    item = models.ForeignKey(AssetItem, on_delete=models.CASCADE,
                             related_name="assignments", db_index=True)

    date_assigned = models.DateField()
    due_back = models.DateField(null=True, blank=True)
    date_returned = models.DateField(null=True, blank=True)

    # stored compute flags
    is_active = models.BooleanField(default=True, db_index=True)   # active = not returned yet
    is_overdue = models.BooleanField(default=False, db_index=True) # due_back passed and not returned

    handover_note = models.TextField(blank=True)
    return_note = models.TextField(blank=True)

    # CompanyOwnedMixin يضيف company؛ سنملؤه تلقائيًا من item.company في clean/save
    company_dependent_relations = ("employee", "item")

    class Meta:
        db_table = "emp_asset_assignment"
        ordering = ["-date_assigned"]
        constraints = [
            models.UniqueConstraint(
                fields=["item"],
                condition=models.Q(is_active=True),
                name="uniq_active_assignment_per_item",
            ),
        ]
        indexes = [
            models.Index(fields=["company", "is_active"]),
            models.Index(fields=["company", "employee", "is_active"]),
        ]

    def __str__(self):
        return f"{self.item.asset_tag} → {getattr(self.employee, 'name', self.employee_id)}"

    def _compute_flags(self):
        self.is_active = self.date_returned is None
        today = timezone.now().date()
        self.is_overdue = bool(self.is_active and self.due_back and self.due_back < today)

    def clean(self):
        super().clean()
        # الشركة = شركة العنصر (denorm)
        if self.item_id and self.item.company_id:
            self.company_id = self.item.company_id
        # تحقق اتساق الشركة بين الموظف والعنصر
        if self.item and self.employee and self.item.company_id != self.employee.company_id:
            raise ValidationError({"item": "Item company must match employee company."})

    @transaction.atomic
    def save(self, *args, **kwargs):
        self._compute_flags()
        # denorm الشركة قبل الحفظ
        if self.item_id and self.item.company_id:
            self.company_id = self.item.company_id
        super().save(*args, **kwargs)

        # تحديث حالة وكاش الحامل على الـ Item
        item = self.item.__class__.objects.select_for_update().get(pk=self.item_id)
        if self.is_active:
            item.current_employee_id = self.employee_id
            item.status = "assigned"
        else:
            # ابحث عن آخر تسليم نشط (غير هذا السجل) إن وجد
            other_active = self.__class__.objects.filter(item=item, is_active=True).exclude(pk=self.pk)\
                               .order_by("-date_assigned").values_list("employee_id", flat=True).first()
            item.current_employee_id = other_active or None
            if not other_active:
                # لا سجلات نشطة: ارجعه للمخزون إن لم يكن مفقود/معطوب
                if item.status == "assigned":
                    item.status = "in_stock"
        item.save(update_fields=["current_employee", "status"])

    def mark_returned(self, date_returned=None, return_note=""):
        self.date_returned = date_returned or timezone.now().date()
        if return_note:
            self.return_note = return_note
        self.save()
