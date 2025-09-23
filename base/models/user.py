# base/models/user.py
from django.db import models
from django.contrib.auth.models import (
    AbstractBaseUser, PermissionsMixin, BaseUserManager, Group, Permission
)
from django.core.exceptions import ValidationError
from .mixins import TimeStampedMixin, ActivableMixin

class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra):
        if not email:
            raise ValueError("Users must have an email address")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.full_clean()
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        return self._create_user(email, password, **extra)

class User(AbstractBaseUser, PermissionsMixin, TimeStampedMixin, ActivableMixin):
    """
    Django version of Odoo's res.users with:
      - OneToOne partner card (inherits pattern)  :contentReference[oaicite:13]{index=13}
      - company  (default)
      - companies (allowed) with constraint: company ∈ companies  :contentReference[oaicite:14]{index=14}
    """
    # Partner card (Odoo _inherits: res.partner -> partner_id). :contentReference[oaicite:15]{index=15}
    partner = models.OneToOneField(
        "base.Partner", on_delete=models.PROTECT, related_name="user", null=True, blank=True
    )

    # Authentication / identity
    email = models.EmailField(unique=True, db_index=True)
    name = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=64, blank=True)

    # Multi-company
    company = models.ForeignKey("base.Company", on_delete=models.PROTECT, related_name="users_default", null=True, blank=True)
    companies = models.ManyToManyField("base.Company", related_name="users", blank=True)

    # Django admin flags
    is_staff = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        db_table = "user"
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["active"]),
        ]

    def __str__(self):
        return self.name or self.email

    def clean(self):
        super().clean()
        # Ensure default company is inside allowed companies (Odoo constraint). :contentReference[oaicite:16]{index=16}
        if self.company and self.pk:
            if not self.companies.filter(pk=self.company_id).exists():
                raise ValidationError({"company": "Default company must be included in allowed companies."})

    # Convenience: mirror some fields from partner if linked (Odoo-esque behavior).
    @property
    def display_name(self):
        return self.name or (self.partner.name if self.partner else self.email)

    def sync_from_partner(self):
        """Optional helper to mirror identity details from partner."""
        if self.partner:
            if not self.name:
                self.name = self.partner.name or ""
            if not self.phone and self.partner.phone:
                self.phone = self.partner.phone
