from django.db import models
from base.models import CompanyOwnedMixin, ActivableMixin, TimeStamped, UserStamped
from django.core.exceptions import ValidationError

class ContractType(TimeStamped, UserStamped, models.Model):
    name = models.CharField(max_length=128)
    code = models.CharField(max_length=128, blank=True)  # store=True in Odoo
    sequence = models.IntegerField(default=10)

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = self.name
        super().save(*args, **kwargs)

    class Meta:
        db_table = "hr_contract_type"
        ordering = ("sequence", "name")
        indexes = [models.Index(fields=["name"]), models.Index(fields=["code"])]
        constraints = [
            models.UniqueConstraint(fields=["name"], name="uniq_contract_type_name")
        ]

    def __str__(self):
        return self.name or self.code or f"Contract #{self.pk}"


class Department(CompanyOwnedMixin, ActivableMixin, TimeStamped, UserStamped, models.Model):
    """
    Odoo-like hr.department

    التعديلات الأساسية:
    - member_count: مُحتسب (مثل Odoo) بدل total_employee المحفوظ.
      أبقينا total_employee كحقل تراثي (legacy) لتوافق أي كود قديم/إشارات حالية، لكن لا نعتمد عليه.
    - فهرس مركّب (company, parent) لتسريع الاستعلامات الهرمية.
    - استعمال ActivableMixin لحقل active.
    """
    name = models.CharField(max_length=255)

    # ملاحظة: الحقل active يأتي من ActivableMixin

    company = models.ForeignKey(
        "base.Company",
        on_delete=models.PROTECT,
        related_name="departments",
    )

    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,  # منع كسر الهرم
        related_name="children",
    )

    manager = models.ForeignKey(
        "hr.Employee",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="managed_departments",
    )

    # العلاقات التي يجب أن تطابق الشركة
    company_dependent_relations = ("parent", "manager")

    # مسارات/أسماء كاملة للشجرة
    complete_name = models.CharField(max_length=1024, blank=True, db_index=True)
    parent_path = models.CharField(max_length=2048, blank=True, db_index=True)

    # خصائص إضافية اختيارية (كما في Odoo)
    note = models.TextField(blank=True)
    color = models.IntegerField(default=0)

    class Meta:
        db_table = "hr_department"
        indexes = [
            # للاستعلامات حسب الشركة والحالة (active) — active يأتي من ActivableMixin
            models.Index(fields=["company", "active"]),
            # لتسريع استعلامات الشجرة
            models.Index(fields=["company", "parent"]),
            models.Index(fields=["parent_path"]),
            models.Index(fields=["complete_name"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "name"],
                name="uniq_department_name_per_company",
            ),
        ]
        ordering = ("complete_name", "name")

    # ========= عدّ مُحتسب بأسلوب Odoo =========
    @property
    def member_count(self) -> int:
        """
        مطابق لمنطق Odoo: عدّ الموظفين النشِطين داخل القسم.
        لا يُحفظ في DB. استخدمه بدل total_employee في الواجهات/التقارير.
        """
        # Employee.active == True فقط
        return self.members.filter(active=True).count()

    # (اختياري) إبقاء alias من أجل توافق مؤقت مع أي قوالب قديمة
    @property
    def member_count_all(self) -> int:
        """إن أردت عدّ كل الأعضاء بغضّ النظر عن active."""
        return self.members.count()

    # ======== منطق الشجرة (same idea as Odoo) ========
    def _recompute_lineage_fields(self):
        """احسب complete_name و parent_path للقسم الحالي فقط."""
        names, ids = [self.name], [str(self.pk)] if self.pk else [""]
        p = self.parent
        while p:
            names.insert(0, p.name)
            ids.insert(0, str(p.pk))
            p = p.parent
        self.complete_name = " / ".join(names)
        self.parent_path = "/".join(ids) + "/"

    def _recompute_subtree(self):
        """
        أعِد حساب complete_name/parent_path لكل الفروع (DFS).
        يفترض أن complete_name/parent_path للحالي صحيحان قبل الاستدعاء.
        """
        stack = list(self.children.all().only("pk", "name", "parent"))
        while stack:
            node = stack.pop()
            names, ids = [node.name], [str(node.pk)]
            p = node.parent
            while p:
                names.insert(0, p.name)
                ids.insert(0, str(p.pk))
                p = p.parent
            node.complete_name = " / ".join(names)
            node.parent_path = "/".join(ids) + "/"
            node.save(update_fields=["complete_name", "parent_path"])
            stack.extend(list(node.children.all().only("pk", "name", "parent")))

    # ======== lifecycle ========
    def save(self, *args, **kwargs):
        # احفظ أولًا لضمان وجود PK عند الحسابات
        super().save(*args, **kwargs)

        # 1) أعِد حساب القسم الحالي (اسم المسار والشجرة)
        self._recompute_lineage_fields()

        # لم نعد نحدّث total_employee هنا — العدّ صار member_count مُحتسبًا.
        super().save(update_fields=["complete_name", "parent_path"])

        # 2) أعِد بناء المتتاليات لكل الأبناء
        self._recompute_subtree()

        # 3) مزامنة مدير موظفي القسم عند تغيير manager (كما كان)
        #    نعمل مقارنة قديمة/جديدة عبر استعلام خفيف
        try:
            if self.pk:
                old_manager_id = type(self).objects.only("manager_id").get(pk=self.pk).manager_id
            else:
                old_manager_id = None
        except type(self).DoesNotExist:
            old_manager_id = None

        if old_manager_id != getattr(self.manager, "id", None):
            from django.apps import apps
            Employee = apps.get_model("hr", "Employee")
            # حسّن تعيين المدير لجميع موظفي القسم النشطين
            Employee.objects.filter(department=self, active=True) \
                .exclude(manager=self.manager) \
                .update(manager=self.manager)

    # ======== التحقق ========
    def clean(self):
        super().clean()

        # التحقق من توافق الشركة بين القسم والأب/المدير
        if self.parent and self.parent.company_id != self.company_id:
            raise ValidationError({"company": "Parent department must belong to the same company."})

        # منع الدوران (Cyclic) في الهرم
        node = self.parent
        while node:
            if node.pk == self.pk:
                raise ValidationError({"parent": "Cyclic department hierarchy is not allowed."})
            node = node.parent

    def __str__(self):
        return self.complete_name or self.name


class WorkLocation(CompanyOwnedMixin, ActivableMixin, TimeStamped, UserStamped, models.Model):
    """
    Odoo hr.work.location: active, name, company, type, address ref, location number.
    """
    name = models.CharField(max_length=255)
    company = models.ForeignKey("base.Company", on_delete=models.PROTECT)
    LOCATION_TYPE = [("home", "Home"), ("office", "Office"), ("other", "Other")]
    location_type = models.CharField(max_length=10, choices=LOCATION_TYPE, default="office")
    address = models.ForeignKey("base.Partner", on_delete=models.PROTECT)
    location_number = models.CharField(max_length=64, blank=True)

    company_dependent_relations = ("address",)

    def clean(self):
        super().clean()
        # check_company مثل Odoo: العنوان يجب أن يطابق الشركة
        if self.address_id and getattr(self.address, "company_id", None) and self.address.company_id != self.company_id:
            from django.core.exceptions import ValidationError
            raise ValidationError({"address": "Address must belong to the same company."})

    class Meta:
        db_table = "hr_work_location"
        constraints = [
            models.UniqueConstraint(fields=["company", "name"], name="uniq_work_location_name_per_company"),
        ]

    def __str__(self):
        return self.name


class Job(CompanyOwnedMixin, ActivableMixin, TimeStamped, UserStamped, models.Model):
    name = models.CharField(max_length=255, db_index=True)
    sequence = models.IntegerField(default=10)
    description = models.TextField(blank=True)  # HTML in Odoo
    requirements = models.TextField(blank=True)

    department = models.ForeignKey("hr.Department", null=True, blank=True, on_delete=models.PROTECT,
                                   related_name="jobs")
    company = models.ForeignKey("base.Company", on_delete=models.PROTECT, related_name="jobs")
    # عدّ تلقائي للعاملين على الوظيفة
    recruiter = models.ForeignKey("base.User", null=True, blank=True, on_delete=models.SET_NULL,
                                  related_name="recruiting_jobs")
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


# لتجميع متقاطع (فرق/مجموعات غير هرمية)
class EmployeeCategory(TimeStamped, UserStamped, models.Model):
    """Odoo-like hr.employee.category (tags)."""
    name = models.CharField(max_length=128, unique=True)
    color = models.PositiveSmallIntegerField(default=1)

    class Meta:
        db_table = "hr_employee_category"

    def __str__(self):
        return self.name


class Employee(CompanyOwnedMixin, ActivableMixin, TimeStamped, UserStamped, models.Model):
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


class EmployeePublic(TimeStamped, models.Model):
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
