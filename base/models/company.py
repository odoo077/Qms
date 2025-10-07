from django.db import models
from .mixins import TimeStampedMixin, ActivableMixin, AddressMixin
from django.core.exceptions import ValidationError

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

    def clean(self):
        """
        سلامة البيانات للشجرة ومطابقة بطاقة الشريك (Odoo-like):

        1) منع كون الشركة أبًا لنفسها.
        2) منع الحلقات (الدورات) في الشجرة (parent ⟶ ... ⟶ self).
        3) إن كانت بطاقة الشريك محددة، يجب أن تكون partner.is_company = True.
        4) مواءمة الشجرة: إن كان لكلٍ من self.parent و self.partner و parent.partner قيم،
           فيُفترض أن يكون partner.parent = parent.partner (تناسق شجرة الشركات وجهات اتصالها).
           (لا نُعدِّل هنا، نتحقق فقط ونُبلغ بخطأ إدخال إن كان هناك عدم اتساق واضح.)
        """

        # 1) منع ذات-الأب
        if self.pk and self.parent_id and self.parent_id == self.pk:
            raise ValidationError({"parent": "Parent company cannot be self."})

        # 2) منع الحلقات
        node = self.parent
        seen = set()
        while node:
            if self.pk and node.pk == self.pk:
                raise ValidationError({"parent": "Cyclic hierarchy is not allowed."})
            if node.pk in seen:
                # حماية إضافية إن حدث تكرار غير متوقع
                raise ValidationError({"parent": "Cyclic hierarchy is not allowed."})
            seen.add(node.pk)
            node = node.parent

        # 3) بطاقة الشريك يجب أن تمثل شركة
        if self.partner_id and getattr(self.partner, "is_company", None) is not True:
            raise ValidationError({"partner": "Linked partner must be of type 'company'."})

        # 4) مواءمة الشجرة بين Company و Partner (تحقق منطقي فقط)
        if self.parent_id and self.partner_id:
            parent_partner = getattr(self.parent, "partner", None)
            if parent_partner and self.partner.parent_id and self.partner.parent_id != parent_partner.id:
                raise ValidationError({
                    "partner": "Partner's parent must match parent company's partner."
                })

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
