# base/models/mixins.py
from django.db import models


class TimeStampedMixin(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        abstract = True


class ActivableMixin(models.Model):
    active = models.BooleanField(default=True, db_index=True)

    class Meta:
        abstract = True


class AddressMixin(models.Model):
    street = models.CharField(max_length=255, blank=True)
    street2 = models.CharField(max_length=255, blank=True)
    zip = models.CharField(max_length=24, blank=True)
    city = models.CharField(max_length=128, blank=True)
    state = models.CharField(max_length=128, blank=True)
    country = models.CharField(max_length=128, blank=True)

    class Meta:
        abstract = True
