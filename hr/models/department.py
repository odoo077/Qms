from django.db import models
from django.core.exceptions import ValidationError
from . import TimeStamped, UserStamped


class Department(TimeStamped, UserStamped, models.Model):
    name = models.CharField(max_length=255)
    active = models.BooleanField(default=True)
    company = models.ForeignKey("base.Company", on_delete=models.PROTECT, related_name="departments")
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="children")

    manager = models.ForeignKey("hr.Employee", null=True, blank=True, on_delete=models.SET_NULL, related_name="managed_departments")

    # store=True in Odoo → persist in DB
    complete_name = models.CharField(max_length=1024, blank=True, db_index=True)
    parent_path = models.CharField(max_length=2048, blank=True, db_index=True)
    total_employee = models.IntegerField(default=0)

    # store=False in Odoo → property only
    @property
    def plans_count(self):
        # TODO: hook into activity plans if you need it
        return 0

    note = models.TextField(blank=True)
    color = models.IntegerField(default=0)

    class Meta:
        db_table = "hr_department"
        indexes = [models.Index(fields=["company", "active"]), models.Index(fields=["parent_path"])]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # recompute stored fields
        names, ids = [self.name], [str(self.pk)]
        p = self.parent
        while p:
            names.insert(0, p.name)
            ids.insert(0, str(p.pk))
            p = p.parent
        self.complete_name = " / ".join(names)
        self.parent_path = "/".join(ids) + "/"
        # recompute employee count
        self.total_employee = self.members.filter(active=True).count()
        super().save(update_fields=["complete_name", "parent_path", "total_employee"])

    def clean(self):
        if self.parent and self.parent.company_id != self.company_id:
            raise ValidationError({"company": "Parent department must belong to the same company."})

    def __str__(self):
        return self.complete_name or self.name
