from django.db import models
from . import TimeStamped, UserStamped


class EmployeePublic(TimeStamped, UserStamped, models.Model):
    """
    Odoo's hr.employee.public is a SQL VIEW (_auto=False).
    Here we model it as unmanaged, and you can create the view in a migration.
    Keep only public/safe fields.
    """
    class Meta:
        db_table = "hr_employee_public"
        managed = False  # Unmanaged (backed by a DB view)

    # mirror safe fields (subset)
    name = models.CharField(max_length=255)
    active = models.BooleanField(default=True)
    company = models.ForeignKey("base.Company", on_delete=models.DO_NOTHING, db_constraint=False)
    department = models.ForeignKey("hr.Department", on_delete=models.DO_NOTHING, null=True, db_constraint=False)
    job = models.ForeignKey("hr.Job", on_delete=models.DO_NOTHING, null=True, db_constraint=False)
    work_contact = models.ForeignKey("base.Partner", on_delete=models.DO_NOTHING, null=True, db_constraint=False)
    work_email = models.EmailField(blank=True)
    work_phone = models.CharField(max_length=64, blank=True)
    mobile_phone = models.CharField(max_length=64, blank=True)
    manager = models.ForeignKey("self", on_delete=models.DO_NOTHING, null=True, db_constraint=False, related_name="subordinates")
    user = models.ForeignKey("base.User", on_delete=models.DO_NOTHING, null=True, db_constraint=False)

    def __str__(self):
        return self.name
