from django.db import models
from . import TimeStamped, UserStamped


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
