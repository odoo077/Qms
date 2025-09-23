# base/models/company.py
from django.db import models
from .mixins import TimeStampedMixin, ActivableMixin, AddressMixin


class Currency(models.Model):
    """Very light currency model so Company can point to one."""
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
    - accepted_users: users allowed to switch to this company
    """
    name = models.CharField(max_length=255, unique=True)
    parent = models.ForeignKey(
        "self", null=True, blank=True, related_name="children", on_delete=models.PROTECT
    )
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=64, blank=True)
    website = models.URLField(blank=True)
    vat = models.CharField("Tax ID", max_length=64, blank=True)
    company_registry = models.CharField("Company ID", max_length=64, blank=True)

    logo = models.ImageField(upload_to="company_logos/", blank=True, null=True)
    primary_color = models.CharField(max_length=16, blank=True)
    secondary_color = models.CharField(max_length=16, blank=True)

    currency = models.ForeignKey(Currency, on_delete=models.PROTECT, null=True, blank=True)

    # Mirror Odoo's "Accepted Users" (res.company.user_ids)
    accepted_users = models.ManyToManyField(
        "base.User", related_name="companies_allowed", blank=True
    )

    class Meta:
        db_table = "company"
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["active"]),
        ]

    def __str__(self):
        return self.name
