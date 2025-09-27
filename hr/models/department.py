from django.db import models
from django.core.exceptions import ValidationError
from base.models.mixins import CompanyOwnedMixin, TimeStamped, UserStamped

class Department(CompanyOwnedMixin, TimeStamped, UserStamped, models.Model):
    name = models.CharField(max_length=255)
    active = models.BooleanField(default=True)
    company = models.ForeignKey("base.Company", on_delete=models.PROTECT, related_name="departments")
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="children")

    manager = models.ForeignKey("hr.Employee", null=True, blank=True, on_delete=models.SET_NULL, related_name="managed_departments")

    company_dependent_relations = ("parent", "manager")

    # store=True in Odoo → persist in DB
    complete_name = models.CharField(max_length=1024, blank=True, db_index=True)
    parent_path = models.CharField(max_length=2048, blank=True, db_index=True)
    total_employee = models.IntegerField(default=0)

    @property
    def plans_count(self):
        return 0

    note = models.TextField(blank=True)
    color = models.IntegerField(default=0)

    class Meta:
        db_table = "hr_department"
        indexes = [
            models.Index(fields=["company", "active"]),
            models.Index(fields=["parent_path"]),
            models.Index(fields=["complete_name"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["company", "name"], name="uniq_department_name_per_company"),
        ]

    def save(self, *args, **kwargs):
        old_manager_id = None
        if self.pk:
            old_manager_id = type(self).objects.only("manager_id").get(pk=self.pk).manager_id

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
        self.total_employee = self.members.filter(active=True).count()
        super().save(update_fields=["complete_name", "parent_path", "total_employee"])

        if old_manager_id != getattr(self.manager, "id", None):
            from django.apps import apps
            Employee = apps.get_model("hr", "Employee")
            Employee.objects.filter(department=self, active=True) \
                .exclude(manager=self.manager) \
                .update(manager=self.manager)

    def clean(self):
        super().clean()
        if self.parent and self.parent.company_id != self.company_id:
            raise ValidationError({"company": "Parent department must belong to the same company."})
        node = self.parent
        while node:
            if node.pk == self.pk:
                raise ValidationError({"parent": "Cyclic department hierarchy is not allowed."})
            node = node.parent

    def __str__(self):
        return self.complete_name or self.name
