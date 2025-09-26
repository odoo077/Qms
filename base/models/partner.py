from django.db import models
from django.core.validators import RegexValidator
from .mixins import TimeStampedMixin, ActivableMixin, AddressMixin, CompanyOwnedMixin



class PartnerCategory(models.Model):
    """Partner tags (res.partner.category)."""
    name = models.CharField(max_length=128)
    color = models.PositiveSmallIntegerField(default=0)
    parent = models.ForeignKey("self", null=True, blank=True, related_name="children", on_delete=models.CASCADE)

    class Meta:
        db_table = "partner_category"
        indexes = [models.Index(fields=["name"])]

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

    name = models.CharField(max_length=255, db_index=True, blank=True)
    is_company = models.BooleanField(default=False)
    company_type = models.CharField(max_length=10, choices=COMPANY_TYPE_CHOICES, default="person")
    type = models.CharField(max_length=10, choices=TYPE_CHOICES, default="contact")

    parent = models.ForeignKey("self", null=True, blank=True, related_name="children", on_delete=models.SET_NULL)
    company = models.ForeignKey("base.Company", null=True, blank=True, on_delete=models.SET_NULL, related_name="partners")

    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=64, blank=True)
    website = models.URLField(blank=True)

    vat = models.CharField("Tax ID", max_length=64, blank=True,
                           validators=[RegexValidator(r"^[^<>]*$", "Invalid characters in VAT")])
    company_registry = models.CharField("Company ID", max_length=64, blank=True)

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
            models.Index(fields=["company_type"]),
            models.Index(fields=["type"]),
            models.Index(fields=["active"]),
        ]

    def __str__(self):
        return self.display_name

    @property
    def display_name(self) -> str:
        if self.parent and not self.is_company:
            parent_name = self.parent.name or ""
            this = self.name or dict(self.TYPE_CHOICES).get(self.type, "").strip()
            joined = f"{parent_name}, {this}".strip(", ")
            return joined
        return (self.name or "").strip()

    @property
    def commercial_partner(self) -> "Partner":
        node = self
        while node and not node.is_company and node.parent:
            node = node.parent
        return node or self
