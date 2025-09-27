from django.db import models
from base.models.mixins import CompanyOwnedMixin, TimeStamped, UserStamped

class Job(CompanyOwnedMixin, TimeStamped, UserStamped, models.Model):
    active = models.BooleanField(default=True)
    name = models.CharField(max_length=255, db_index=True)
    sequence = models.IntegerField(default=10)
    description = models.TextField(blank=True)   # HTML in Odoo
    requirements = models.TextField(blank=True)

    department = models.ForeignKey("hr.Department", null=True, blank=True, on_delete=models.PROTECT, related_name="jobs")
    company = models.ForeignKey("base.Company", on_delete=models.PROTECT, related_name="jobs")
    recruiter = models.ForeignKey("base.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="recruiting_jobs")
    contract_type = models.ForeignKey("hr.ContractType", null=True, blank=True, on_delete=models.SET_NULL)

    company_dependent_relations = ("department",)

    no_of_recruitment = models.PositiveIntegerField(default=1)

    # store=True in Odoo → persist & recompute
    no_of_employee = models.PositiveIntegerField(default=0, editable=False)
    expected_employees = models.PositiveIntegerField(default=0, editable=False)

    @property
    def allowed_user_ids(self):
        return []

    class Meta:
        db_table = "hr_job"
        indexes = [
            models.Index(fields=["company", "active"]),
            models.Index(fields=["department", "active"]),
            models.Index(fields=["name"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["name", "company", "department"], name="uniq_job_name_company_department"),
        ]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        count = self.employee_set.filter(active=True).count()
        self.no_of_employee = count
        self.expected_employees = count + (self.no_of_recruitment or 0)
        super().save(update_fields=["no_of_employee", "expected_employees"])

    def __str__(self):
        return self.name
