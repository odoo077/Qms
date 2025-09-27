from django.db import models
from django.core.exceptions import ValidationError
from base.models.mixins import CompanyOwnedMixin, TimeStamped, UserStamped

class Employee(CompanyOwnedMixin, TimeStamped, UserStamped, models.Model):
    active = models.BooleanField(default=True)

    company = models.ForeignKey("base.Company", on_delete=models.PROTECT, related_name="employees")
    name = models.CharField(max_length=255, db_index=True)
    user = models.ForeignKey("base.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="employees")

    department = models.ForeignKey("hr.Department", null=True, blank=True, on_delete=models.SET_NULL, related_name="members")
    job = models.ForeignKey("hr.Job", null=True, blank=True, on_delete=models.SET_NULL, related_name="employee_set")
    manager = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="children")
    coach = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="coachees")

    work_contact = models.ForeignKey("base.Partner", null=True, blank=True, on_delete=models.SET_NULL, related_name="employee_work_contact")

    # جميع العلاقات يجب أن تطابق شركة الموظف
    company_dependent_relations = ("department", "job", "manager", "coach", "work_location", "work_contact")

    # store=True in Odoo (related fields)
    work_email = models.EmailField(blank=True)
    work_phone = models.CharField(max_length=64, blank=True)
    mobile_phone = models.CharField(max_length=64, blank=True)

    # store=True in Odoo
    birthday_public_display_string = models.CharField(max_length=64, blank=True)
    coach_id_cache = models.CharField(max_length=255, blank=True)  # simulate Odoo store=True on coach_id compute

    # transient presence fields (store=False in Odoo)
    @property
    def hr_presence_state(self):
        return "archive" if not self.active else "present"

    @property
    def hr_icon_display(self):
        return "fa-user"

    @property
    def show_hr_icon_display(self):
        return self.active

    work_location = models.ForeignKey("hr.WorkLocation", null=True, blank=True, on_delete=models.SET_NULL, related_name="employees")

    categories = models.ManyToManyField("hr.EmployeeCategory", blank=True, related_name="employees")

    barcode = models.CharField(max_length=64, blank=True, unique=True)
    pin = models.CharField(max_length=32, blank=True)

    class Meta:
        db_table = "hr_employee"
        indexes = [
            models.Index(fields=["company", "active"]),
            models.Index(fields=["name"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["user", "company"], name="uniq_user_per_company"),
        ]

    def clean(self):
        super().clean()
        # FK يجب أن تطابق الشركة
        checks = (
            ("department", getattr(self, "department", None)),
            ("job", getattr(self, "job", None)),
            ("work_location", getattr(self, "work_location", None)),
            ("work_contact", getattr(self, "work_contact", None)),
        )
        for fname, rel in checks:
            if rel and getattr(rel, "company_id", None) and rel.company_id != self.company_id:
                raise ValidationError({fname: "Must match employee company."})
        if self.manager and self.manager.company_id != self.company_id:
            raise ValidationError({"manager": "Manager must match employee company."})
        if self.coach and self.coach.company_id != self.company_id:
            raise ValidationError({"coach": "Coach must match employee company."})

    def save(self, *args, **kwargs):
        # recompute birthday display string
        if self.birthday_public_display_string == "" and hasattr(self, "birthday") and self.birthday:
            self.birthday_public_display_string = self.birthday.strftime("%d %B")
        # recompute coach cache
        self.coach_id_cache = str(self.coach_id) if self.coach_id else ""
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name
