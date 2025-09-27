from django.db import models
from base.models.mixins import TimeStamped, UserStamped

class ContractType(TimeStamped, UserStamped, models.Model):
    name = models.CharField(max_length=128)
    code = models.CharField(max_length=128, blank=True)  # store=True in Odoo
    sequence = models.IntegerField(default=10)

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = self.name
        super().save(*args, **kwargs)

    class Meta:
        db_table = "hr_contract_type"
        ordering = ("sequence", "name")
        indexes = [models.Index(fields=["name"]), models.Index(fields=["code"])]
        constraints = [
            models.UniqueConstraint(fields=["name"], name="uniq_contract_type_name")
        ]

    def __str__(self):
        return self.name or self.code or f"Contract #{self.pk}"
