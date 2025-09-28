from django.core.exceptions import ValidationError
from django.db import models

from base.models.mixins import CompanyOwnedMixin, TimeStamped, UserStamped


class Employee(CompanyOwnedMixin, TimeStamped, UserStamped, models.Model):
    active = models.BooleanField(default=True)

    company = models.ForeignKey(
        "base.Company",
        on_delete=models.PROTECT,
        related_name="employees",
    )
    name = models.CharField(max_length=255, db_index=True)
    user = models.ForeignKey(
        "base.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="employees",
    )

    department = models.ForeignKey(
        "hr.Department",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="members",
    )
    job = models.ForeignKey(
        "hr.Job",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="employee_set",
    )
    manager = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="children",
    )
    coach = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="coachees",
    )

    work_contact = models.ForeignKey(
        "base.Partner",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="employee_work_contact",
    )

    # جميع العلاقات يجب أن تطابق شركة الموظف
    company_dependent_relations = (
        "department",
        "job",
        "manager",
        "coach",
        "work_location",
        "work_contact",
    )

    # store=True in Odoo (related fields)
    work_email = models.EmailField(blank=True)
    work_phone = models.CharField(max_length=64, blank=True)
    mobile_phone = models.CharField(max_length=64, blank=True)

    # --- Private / Personal ---
    private_phone = models.CharField(max_length=64, blank=True)  # Odoo: private_phone
    private_email = models.EmailField(blank=True)  # Odoo: private_email
    birthday = models.DateField(null=True, blank=True)  # Odoo: birthday
    place_of_birth = models.CharField(max_length=255, blank=True)
    # store=True in Odoo
    birthday_public_display_string = models.CharField(max_length=64, blank=True)
    coach_id_cache = models.CharField(
        max_length=255,
        blank=True,
    )  # simulate Odoo store=True on coach_id compute

    # --- Emergency ---
    emergency_contact = models.CharField(max_length=255, blank=True)
    emergency_phone = models.CharField(max_length=64, blank=True)

    # --- Education / Visa / Permit ---
    certificate = models.CharField(max_length=64, blank=True)  # Bachelor/Master/...
    study_field = models.CharField(max_length=128, blank=True)
    study_school = models.CharField(max_length=128, blank=True)

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

    work_location = models.ForeignKey(
        "hr.WorkLocation",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="employees",
    )

    categories = models.ManyToManyField(
        "hr.EmployeeCategory",
        blank=True,
        related_name="employees",
    )

    barcode = models.CharField(max_length=64, blank=True, null=True)
    pin = models.CharField(max_length=32, blank=True)

    # ==== داخل hr/models/employee.py ضمن class Employee ====
    class Meta:
        db_table = "hr_employee"
        indexes = [
            models.Index(fields=["company", "active"]),
            models.Index(fields=["name"]),
            models.Index(fields=["active"]),
            models.Index(fields=["department"]),
        ]
        constraints = [
            # barcode فريد لكل شركة عند تعبئته (يسمح بتعدد NULL)
            models.UniqueConstraint(
                fields=["company", "barcode"],
                name="uniq_employee_barcode_per_company",
                condition=models.Q(barcode__isnull=False),
            ),
            # منع أن يكون الموظف مدير نفسه
            models.CheckConstraint(
                name="employee_manager_not_self",
                check=~models.Q(pk=models.F("manager")),
            ),
            # منع أن يكون الموظف مُرشِد نفسه
            models.CheckConstraint(
                name="employee_coach_not_self",
                check=~models.Q(pk=models.F("coach")),
            ),
            # (اختياري) pin فريد لكل شركة عند تعبئته
            models.UniqueConstraint(
                fields=["company", "pin"],
                name="uniq_employee_pin_per_company",
                condition=models.Q(pin__gt=""),
            ),
        ]

    def clean(self):
        super().clean()

        # 1) العلاقات التي يجب أن تطابق شركة الموظف
        checks = (
            ("department", getattr(self, "department", None)),
            ("job", getattr(self, "job", None)),
            ("work_location", getattr(self, "work_location", None)),
            ("work_contact", getattr(self, "work_contact", None)),
        )
        for fname, rel in checks:
            if rel and getattr(rel, "company_id", None) and rel.company_id != self.company_id:
                raise ValidationError({fname: "Must match employee company."})

        if self.manager and getattr(self.manager, "company_id", None) != self.company_id:
            raise ValidationError({"manager": "Manager must match employee company."})
        if self.coach and getattr(self.coach, "company_id", None) != self.company_id:
            raise ValidationError({"coach": "Coach must match employee company."})

        # 2) منع self-reference منطقياً (بالإضافة لقيد DB)
        if self.pk:
            if self.manager_id and self.manager_id == self.pk:
                raise ValidationError({"manager": "Employee cannot be their own manager."})
            if self.coach_id and self.coach_id == self.pk:
                raise ValidationError({"coach": "Employee cannot be their own coach."})

        # 3) تحقّق صيغة الـ Barcode عند تعبئته (مثل Odoo: حروف/أرقام وبحد أقصى 18)
        if self.barcode:
            import re

            if not (re.match(r"^[A-Za-z0-9]+$", self.barcode) and len(self.barcode) <= 18):
                raise ValidationError({"barcode": "Badge ID must be alphanumeric and ≤ 18 chars."})

    def save(self, *args, **kwargs):
        # recompute birthday display string
        if self.birthday_public_display_string == "" and hasattr(self, "birthday") and self.birthday:
            self.birthday_public_display_string = self.birthday.strftime("%d %B")

        # recompute coach cache
        self.coach_id_cache = str(self.coach_id) if self.coach_id else ""

        if self.barcode == "":
            self.barcode = None

        super().save(*args, **kwargs)

    def __str__(self):
        return self.name
