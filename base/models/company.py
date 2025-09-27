from django.db import models
from .mixins import TimeStampedMixin, ActivableMixin, AddressMixin


class Currency(models.Model):
    """Very light currency model so Company can point to one (Odoo-like)."""
    code = models.CharField(max_length=10, unique=True)  # e.g., IQD, USD
    name = models.CharField(max_length=64, blank=True)

    def __str__(self):
        return self.code


class Company(TimeStampedMixin, ActivableMixin, AddressMixin):
    """
    Django flavor of Odoo's res.company.
    - parent/children tree
    - identity details + reporting fields
    - default currency
    - accepted_users: users allowed to switch to this company (Odoo-like)
    """

    # داخل class Company:
    SYNCED_WITH_PARTNER_FIELDS = (
        "name", "email", "phone", "website",
        "street", "street2", "city", "state", "zip", "country",
        "vat", "company_registry",
    )

    name = models.CharField(max_length=255, unique=True)
    parent = models.ForeignKey(
        "self", null=True, blank=True, related_name="children", on_delete=models.PROTECT
    )
    sequence = models.PositiveIntegerField(default=10, db_index=True)
    parent_path = models.CharField(max_length=255, blank=True, db_index=True)

    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=64, blank=True)
    website = models.URLField(blank=True)
    vat = models.CharField("Tax ID", max_length=64, blank=True)
    company_registry = models.CharField("Company ID", max_length=64, blank=True)

    logo = models.ImageField(upload_to="company_logos/", blank=True, null=True)
    primary_color = models.CharField(max_length=16, blank=True)
    secondary_color = models.CharField(max_length=16, blank=True)

    currency = models.ForeignKey(Currency, on_delete=models.PROTECT, null=True, blank=True)

    # ✅ جديد: جهة الاتصال المقابلة للشركة
    partner = models.OneToOneField(
        "base.Partner", null=True, blank=True,
        on_delete=models.PROTECT, related_name="company_profile"
    )

    accepted_users = models.ManyToManyField(
        "base.User", related_name="companies_allowed", blank=True
    )

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        # حساب المسار المادّي بعد وجود pk
        path = f"{self.pk}/"
        if self.parent and self.parent.parent_path:
            path = f"{self.parent.parent_path}{self.pk}/"
        elif self.parent:
            path = f"{self.parent.pk}/{self.pk}/"
        if self.parent_path != path:
            self.parent_path = path
            super().save(update_fields=["parent_path"])

    class Meta:
        db_table = "company"
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["active"]),
        ]

    def __str__(self):
        return self.name
