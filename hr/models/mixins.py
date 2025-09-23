# hr/models/mixins.py
from django.db import models
from django.utils import timezone


class TimeStamped(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)  # create_date
    updated_at = models.DateTimeField(auto_now=True, db_index=True)      # write_date
    class Meta:
        abstract = True


# Optional: only if you want Odoo-like create_uid/write_uid
class UserStamped(models.Model):
    created_by = models.ForeignKey("base.User", null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="%(class)s_created")
    updated_by = models.ForeignKey("base.User", null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="%(class)s_updated")

    class Meta:
        abstract = True
