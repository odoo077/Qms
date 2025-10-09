# hr/models/employee.py
from django.core.exceptions import ValidationError
from django.db import models
from base.models.mixins import (
    CompanyOwnedMixin,
    TimeStamped,
    UserStamped,
    ActivableMixin,  # يوفر الحقل active افتراضيًا
)

class Employee(CompanyOwnedMixin,ActivableMixin, TimeStamped, UserStamped, models.Model):
    """Odoo-like hr.employee"""

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
        related_name="managed_employees"
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

    # العنوان الشخصي (المنزل) - لا يتبع شركة محددة
    address_home = models.ForeignKey(
        "base.Partner",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="employee_home_address",
        help_text="العنوان الشخصي للموظف (Partner شخصي لا يتبع الشركة).",
    )

    # العلاقات التي يجب أن تطابق شركة الموظف
    company_dependent_relations = (
        "department",
        "job",
        "manager",
        "coach",
        "work_location",
        "work_contact",
    )

    # store=True في Odoo (حقول مشتقة)
    work_email = models.EmailField(blank=True)
    work_phone = models.CharField(max_length=64, blank=True)
    mobile_phone = models.CharField(max_length=64, blank=True)

    # --- بيانات خاصة / شخصية ---
    private_phone = models.CharField(max_length=64, blank=True)
    private_email = models.EmailField(blank=True)
    birthday = models.DateField(null=True, blank=True)
    place_of_birth = models.CharField(max_length=255, blank=True)
    birthday_public_display_string = models.CharField(max_length=64, blank=True)
    coach_id_cache = models.CharField(max_length=255, blank=True)

    # --- بيانات الطوارئ ---
    emergency_contact = models.CharField(max_length=255, blank=True)
    emergency_phone = models.CharField(max_length=64, blank=True)

    # --- بيانات التعليم / الإقامة ---
    certificate = models.CharField(max_length=64, blank=True)
    study_field = models.CharField(max_length=128, blank=True)
    study_school = models.CharField(max_length=128, blank=True)

    # --- الحقول الإضافية (اختيارية لتوسيع Employee مثل Odoo) ---
    marital_status = models.CharField(
        max_length=32,
        blank=True,
        choices=[
            ("single", "Single"),
            ("married", "Married"),
            ("divorced", "Divorced"),
            ("widow", "Widow"),
        ],
    )
    gender = models.CharField(
        max_length=16,
        blank=True,
        choices=[("male", "Male"), ("female", "Female")],
    )
    children = models.PositiveIntegerField(
        default=0,
        help_text="Number of children",
    )

    identification_id = models.CharField(
        max_length=64,
        blank=True,
        help_text="National ID / Identification",
    )

    passport_id = models.CharField(
        max_length=64,
        blank=True,
        help_text="Passport number",
    )

    bank_account = models.CharField(
        max_length=128,
        blank=True,
        help_text="Bank account details",
    )

    car = models.CharField(
        max_length=128,
        blank=True,
        help_text="Vehicle information (if applicable)",
    )
    # --- نهاية الحقول الإضافية ---

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

    class Meta:
        db_table = "hr_employee"
        indexes = [
            models.Index(fields=["company", "active"]),
            models.Index(fields=["name"]),
            models.Index(fields=["active"]),
            models.Index(fields=["department"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "barcode"],
                name="uniq_employee_barcode_per_company",
                condition=models.Q(barcode__isnull=False),
            ),
            models.CheckConstraint(
                name="employee_manager_not_self",
                check=~models.Q(pk=models.F("manager")),
            ),
            models.CheckConstraint(
                name="employee_coach_not_self",
                check=~models.Q(pk=models.F("coach")),
            ),
            models.UniqueConstraint(
                fields=["company", "pin"],
                name="uniq_employee_pin_per_company",
                condition=models.Q(pin__gt=""),
            ),
        ]

        permissions = [
            ("approve_employee", "Can approve employee record"),
            ("view_private_fields", "Can view employee private fields"),
        ]

    # ======= الحقول المحسوبة / الخاصة ==========
    @property
    def hr_presence_state(self):
        return "archive" if not self.active else "present"

    @property
    def hr_icon_display(self):
        return "fa-user"

    @property
    def show_hr_icon_display(self):
        return self.active

    # ========= التحقق =========
    def clean(self):
        super().clean()

        # العلاقات التي يجب أن تتبع نفس الشركة
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

        # منع self-reference منطقياً
        if self.pk:
            if self.manager_id and self.manager_id == self.pk:
                raise ValidationError({"manager": "Employee cannot be their own manager."})
            if self.coach_id and self.coach_id == self.pk:
                raise ValidationError({"coach": "Employee cannot be their own coach."})

        # تحقق من صيغة الـ Barcode
        if self.barcode:
            import re
            if not (re.match(r"^[A-Za-z0-9]+$", self.barcode) and len(self.barcode) <= 18):
                raise ValidationError({"barcode": "Badge ID must be alphanumeric and ≤ 18 chars."})

    # ========= الحفظ =========
    def save(self, *args, **kwargs):
        # تحديث عرض تاريخ الميلاد
        if self.birthday:
            self.birthday_public_display_string = self.birthday.strftime("%d %B")

        # تحديث كاش المدرب
        self.coach_id_cache = str(self.coach_id) if self.coach_id else ""

        if self.barcode == "":
            self.barcode = None

        # في حال وجود address_home → اشتق البريد والهاتف الخاص
        if self.address_home:
            if not self.private_email and getattr(self.address_home, "email", None):
                self.private_email = self.address_home.email
            if not self.private_phone and getattr(self.address_home, "phone", None):
                self.private_phone = self.address_home.phone

        super().save(*args, **kwargs)

    @property
    def current_skills(self):
        from skills.models import HrEmployeeSkill
        return HrEmployeeSkill.current_for_employee(self.id)

    def __str__(self):
        return self.name
