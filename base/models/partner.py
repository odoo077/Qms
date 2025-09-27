from django.db import models
from django.core.validators import RegexValidator
from .mixins import TimeStampedMixin, ActivableMixin, AddressMixin, CompanyOwnedMixin
from django.core.exceptions import ValidationError


class PartnerCategory(models.Model):
    """Partner tags (res.partner.category)."""
    name = models.CharField(max_length=128)
    color = models.PositiveSmallIntegerField(default=0)
    parent = models.ForeignKey("self", null=True, blank=True, related_name="children", on_delete=models.CASCADE)
    complete_name = models.CharField(max_length=256, blank=True, db_index=True)
    parent_path = models.CharField(max_length=255, blank=True, db_index=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # materialized path: "1/5/9/"
        new_path = f"{self.pk}/"
        if self.parent and self.parent.parent_path:
            new_path = f"{self.parent.parent_path}{self.pk}/"
        elif self.parent:
            new_path = f"{self.parent.pk}/{self.pk}/"
        # حدّث المسار والاسم الكامل مرة ثانية فقط عند الحاجة
        new_complete = self.name if not self.parent else f"{self.parent.complete_name} / {self.name}"
        updates = []
        if self.parent_path != new_path:
            self.parent_path = new_path
            updates.append("parent_path")
        if self.complete_name != new_complete:
            self.complete_name = new_complete
            updates.append("complete_name")
        if updates:
            super(PartnerCategory, self.__class__).save(self, update_fields=updates)

    class Meta:
        db_table = "partner_category"
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["complete_name"]),
            models.Index(fields=["parent_path"]),
        ]

    def __str__(self):
        return self.name


class Partner(CompanyOwnedMixin, TimeStampedMixin, ActivableMixin, AddressMixin):
    """
    Django flavor of Odoo's res.partner.
    - companies & persons share same table
    - company/person switch via company_type
    - parent link to represent a company's contacts
    - commercial_partner (computed-like property)
    """

    TYPE_CHOICES = [
        ("contact", "Contact"),
        ("invoice", "Invoice"),
        ("delivery", "Delivery"),
        ("other", "Other"),
    ]
    COMPANY_TYPE_CHOICES = [
        ("person", "Person"),
        ("company", "Company"),
    ]

    # Identity
    name = models.CharField(max_length=255, db_index=True, blank=True)
    display_name = models.CharField(max_length=512, blank=True, db_index=True)
    is_company = models.BooleanField(default=False)
    company_type = models.CharField(max_length=10, choices=COMPANY_TYPE_CHOICES, default="person")
    type = models.CharField(max_length=10, choices=TYPE_CHOICES, default="contact")

    # Hierarchy
    parent = models.ForeignKey(
        "self", null=True, blank=True, related_name="children", on_delete=models.SET_NULL
    )
    # نسخة مسطّحة من parent.company لتجنّب أي JOIN في القيود/الاستعلامات
    parent_company = models.ForeignKey(
        "base.Company", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="partner_children_all", editable=False, db_index=True,
    )

    # Company ownership (company-dependent)
    company = models.ForeignKey(
        "base.Company", null=True, blank=True, on_delete=models.SET_NULL, related_name="partners"
    )

    # Contact info
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=64, blank=True)
    website = models.URLField(blank=True)

    # Fiscal identity
    vat = models.CharField(
        "Tax ID", max_length=64, blank=True,
        validators=[RegexValidator(r"^[^<>]*$", "Invalid characters in VAT")]
    )
    company_registry = models.CharField("Company ID", max_length=64, blank=True)

    # Categorization / relations
    categories = models.ManyToManyField(PartnerCategory, related_name="partners", blank=True)
    salesperson = models.ForeignKey(
        "base.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="customer_set"
    )
    employee = models.BooleanField(default=False)

    # علاقات يجب أن تُطابق شركتها نفس شركة السجل (للتحقق cross-company)
    company_dependent_relations = ("parent",)

    class Meta:
        db_table = "partner"
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["display_name"]),
            models.Index(fields=["company_type"]),
            models.Index(fields=["type"]),
            models.Index(fields=["active"]),
            models.Index(fields=["parent_company", "company_type", "type"]),
        ]
        # قيد DB حقيقي بدون أي JOIN: يعتمد على الحقل المسطّح parent_company
        constraints = [
            models.CheckConstraint(
                name="partner_parent_company_match",
                check=models.Q(parent__isnull=True) | models.Q(company=models.F("parent_company")),
                violation_error_message="Parent and child must belong to the same company.",
            ),
        models.UniqueConstraint(
            fields=["company", "vat"],
            name="partner_unique_vat_per_company",
            condition=models.Q(vat__gt=""),
            violation_error_message="VAT must be unique per company when set.",
        ),
        models.UniqueConstraint(
            fields=["company", "company_registry"],
            name="partner_unique_registry_per_company",
            condition=models.Q(company_registry__gt=""),
            violation_error_message="Company Registry must be unique per company when set.",
        )

        ]

    # -------- Validation & Persistence --------
    def clean(self):
        # صيانة الحقل المسطّح ليستعمله قيد DB والفلاتر بدون JOIN
        self.parent_company = (
            self.parent.company if (self.parent_id and self.parent and self.parent.company_id) else None
        )
        # نفّذ تحققات CompanyOwnedMixin (تشمل تطابق الشركة لعلاقات company_dependent_relations)
        super().clean()

    def compute_display_name(self) -> str:
        if self.parent_id and not self.is_company:
            parent_name = (self.parent.name or "").strip()
            this = (self.name or dict(self.TYPE_CHOICES).get(self.type, "")).strip()
            return f"{parent_name}, {this}".strip(", ")
        return (self.name or "").strip()

    def save(self, *args, **kwargs):
        # صيانة الحقل المسطّح
        self.parent_company = (
            self.parent.company if (self.parent_id and self.parent and self.parent.company_id) else None
        )
        # توريث salesperson من الأب إذا كان شخصًا ولم يُحدد
        if not self.is_company and self.parent_id and not self.salesperson_id:
            self.salesperson_id = getattr(self.parent, "salesperson_id", None)

        # تحقّق + الاسم المعروض
        self.clean()
        self.display_name = self.compute_display_name()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.display_name or self.name or ""

    # -------- Odoo-like helpers --------
    @property
    def commercial_partner(self) -> "Partner":
        node = self
        while node and not node.is_company and node.parent:
            node = node.parent
        return node or self