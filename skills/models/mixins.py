from django.db import models


class TimeStamped(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)   # Odoo create_date
    updated_at = models.DateTimeField(auto_now=True, db_index=True)       # Odoo write_date
    class Meta:
        abstract = True
