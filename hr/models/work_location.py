from django.db import models
from base.models.mixins import CompanyOwnedMixin, TimeStamped, UserStamped

class WorkLocation(CompanyOwnedMixin, TimeStamped, UserStamped, models.Model):
    """
    Odoo hr.work.location: active, name, company, type, address ref, location number.
    """
    active = models.BooleanField(default=True)
    name = models.CharField(max_length=255)
    company = models.ForeignKey("base.Company", on_delete=models.PROTECT)
    LOCATION_TYPE = [("home", "Home"), ("office", "Office"), ("other", "Other")]
    location_type = models.CharField(max_length=10, choices=LOCATION_TYPE, default="office")
    address = models.ForeignKey("base.Partner", on_delete=models.PROTECT)
    location_number = models.CharField(max_length=64, blank=True)

    company_dependent_relations = ("address",)

    def clean(self):
        super().clean()
        # check_company مثل Odoo: العنوان يجب أن يطابق الشركة
        if self.address_id and getattr(self.address, "company_id", None) and self.address.company_id != self.company_id:
            from django.core.exceptions import ValidationError
            raise ValidationError({"address": "Address must belong to the same company."})

    class Meta:
        db_table = "hr_work_location"
        constraints = [
            models.UniqueConstraint(fields=["company", "name"], name="uniq_work_location_name_per_company"),
        ]

    def __str__(self):
        return self.name
