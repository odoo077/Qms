# hr/models.py
# ============================================================
# موديلات الموارد البشرية — Odoo-like
# - Company scope عبر CompanyOwnedMixin
# - صلاحيات كائنية عبر AccessControlledMixin (على Employee)
# - ربط Partner للموظف (سيُدار عبر الإشارات)
# - حقول وفهارس وقيود تشبه Odoo
# ============================================================

from __future__ import annotations

from django.db import models
from django.core.exceptions import ValidationError

# مكسنات وبُنى أساسية من تطبيق base
from base.models import (
    CompanyOwnedMixin,     # يضمن company + فحوص التوافق
    ActivableMixin,        # يحوي active=BooleanField
    TimeStampedMixin,           # created_at / updated_at
    UserStampedMixin,           # created_by / updated_by
)

# ACL (صلاحيات كائنية) — نطبّقها على Employee تحديدًا
from base.acl import AccessControlledMixin


# ------------------------------------------------------------
# ContractType — نوع عقد العمل (بسيط ومباشر)
# ------------------------------------------------------------
class ContractType(TimeStampedMixin, UserStampedMixin, models.Model):
    name = models.CharField(max_length=128)
    code = models.CharField(max_length=128, blank=True)   # store=True في Odoo
    sequence = models.IntegerField(default=10)

    def save(self, *args, **kwargs):
        # سلوك عملي: إن لم تُحدّد code، خذ الاسم
        if not self.code:
            self.code = self.name
        super().save(*args, **kwargs)

    class Meta:
        db_table = "hr_contract_type"
        # مثل Odoo: الترتيب بالـ sequence فقط
        ordering = ("sequence",)
        indexes = [
            models.Index(fields=["name"], name="hr_contract_name_idx"),
            models.Index(fields=["code"], name="hr_contract_code_idx"),
        ]
        # constraints = []

    def __str__(self):
        return self.name or self.code or f"ContractType #{self.pk}"


# ------------------------------------------------------------
# Department — قسم هرمي على مستوى الشركة
# ------------------------------------------------------------
class Department(CompanyOwnedMixin, ActivableMixin, TimeStampedMixin, UserStampedMixin, models.Model):
    """
    Odoo-like hr.department
    - شجرة أقسام لكل شركة
    - complete_name و parent_path محسوبات ومخزّنة (لأداء أفضل)
    """
    name = models.CharField(max_length=255)

    company = models.ForeignKey(
        "base.Company",
        on_delete=models.PROTECT,
        related_name="departments",
    )

    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,  # منع كسر الهرم بحذف الأب
        related_name="children",
    )

    manager = models.ForeignKey(
        "hr.Employee",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="managed_departments",
    )

    # علاقات يجب أن تتبع نفس الشركة (يُفحص عبر CompanyOwnedMixin)
    company_dependent_relations = ("parent", "manager")

    # حقول الشجرة
    complete_name = models.CharField(max_length=1024, blank=True, db_index=True)
    parent_path = models.CharField(max_length=2048, blank=True, db_index=True)

    # خصائص إضافية اختيارية
    note = models.TextField(blank=True)
    color = models.IntegerField(default=0)

    class Meta:
        db_table = "hr_department"
        indexes = [
            models.Index(fields=["company", "active"], name="hr_departme_company_active_idx"),
            models.Index(fields=["company", "parent"], name="hr_departme_company_parent_idx"),
            models.Index(fields=["parent_path"], name="hr_departme_parent_path_idx"),
            models.Index(fields=["complete_name"], name="hr_departme_complete_name_idx"),
        ]
        # constraints = []
        ordering = ("name",)

    # ---------- خواص محسوبة ----------
    @property
    def member_count(self) -> int:
        """عدد الموظفين النشِطين في القسم (سلوك Odoo)."""
        return self.members.filter(active=True).count()

    # ---------- منطق الشجرة ----------
    def _recompute_lineage_fields(self):
        """إعادة حساب اسم المسار والمسار الأبوي للسجل الحالي فقط."""
        names, ids = [self.name], [str(self.pk) if self.pk else ""]
        p = self.parent
        while p:
            names.insert(0, p.name)
            ids.insert(0, str(p.pk))
            p = p.parent
        self.complete_name = " / ".join(names)
        self.parent_path = "/".join(ids) + "/"

    def _recompute_subtree(self):
        """إعادة حساب complete_name/parent_path لكل الفروع (DFS)."""
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

    # ---------- lifecycle ----------
    def save(self, *args, **kwargs):
        # المدير السابق قبل الحفظ
        prev_manager_id = None
        if self.pk:
            prev_manager_id = type(self).objects.only("manager_id").filter(pk=self.pk) \
                .values_list("manager_id", flat=True).first()

        super().save(*args, **kwargs)  # 1) احفظ للحصول على PK
        self._recompute_lineage_fields()
        super().save(update_fields=["complete_name", "parent_path"])  # 2) خزّن الحقول المحسوبة
        self._recompute_subtree()  # 3) حدّث الفروع

        # 4) إن تغيّر المدير، لا ننسخ المدير تلقائيًا لأعضاء القسم
        #    (Odoo-like) — مدير الموظف قرار مستقل ولا يُشتق تلقائيًا من مدير القسم.
        #    لذا لا يوجد أي تحديث جماعي هنا.

    # ---------- تحقق ----------
    def clean(self):
        super().clean()

        if self.parent and self.parent.company_id != self.company_id:
            raise ValidationError({"company": "Parent department must belong to the same company."})

        # منع الدوران في الهرم
        node = self.parent
        while node:
            if node.pk == self.pk:
                raise ValidationError({"parent": "Cyclic department hierarchy is not allowed."})
            node = node.parent

    def __str__(self):
        return self.complete_name or self.name


# ------------------------------------------------------------
# WorkLocation — موقع عمل (مكتب/منزل/غيره)
# ------------------------------------------------------------
class WorkLocation(CompanyOwnedMixin, ActivableMixin, TimeStampedMixin, UserStampedMixin, models.Model):
    name = models.CharField(max_length=255)
    company = models.ForeignKey("base.Company", on_delete=models.PROTECT)

    LOCATION_TYPE = [("home", "Home"), ("office", "Office"), ("other", "Other")]
    location_type = models.CharField(max_length=10, choices=LOCATION_TYPE, default="office")

    address = models.ForeignKey("base.Partner", on_delete=models.PROTECT)
    location_number = models.CharField(max_length=64, blank=True)

    company_dependent_relations = ("address",)

    def clean(self):
        super().clean()
        # العنوان يجب أن يتبع نفس الشركة (سلوك Odoo)
        if self.address_id and getattr(self.address, "company_id", None) and self.address.company_id != self.company_id:
            raise ValidationError({"address": "Address must belong to the same company."})

    class Meta:
        db_table = "hr_work_location"
        # constraints = []
        ordering = ("name",)

    def __str__(self):
        return self.name


# ------------------------------------------------------------
# Job — مسمى وظيفي
# ------------------------------------------------------------
class Job(CompanyOwnedMixin, ActivableMixin, TimeStampedMixin, UserStampedMixin, models.Model):
    name = models.CharField(max_length=255, db_index=True)
    sequence = models.IntegerField(default=10)
    description = models.TextField(blank=True)   # HTML في Odoo
    requirements = models.TextField(blank=True)

    department = models.ForeignKey(
        "hr.Department",
        null=True, blank=True,
        on_delete=models.PROTECT,
        related_name="jobs",
    )
    company = models.ForeignKey("base.Company", on_delete=models.PROTECT, related_name="jobs")

    recruiter = models.ForeignKey(
        "base.User", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="recruiting_jobs",
    )

    contract_type = models.ForeignKey("hr.ContractType", null=True, blank=True, on_delete=models.SET_NULL)

    company_dependent_relations = ("department",)

    no_of_recruitment = models.PositiveIntegerField(default=1)

    # store=True في Odoo → تُحدَّث بعد الحفظ
    no_of_employee = models.PositiveIntegerField(default=0, editable=False)
    expected_employees = models.PositiveIntegerField(default=0, editable=False)

    class Meta:
        db_table = "hr_job"
        indexes = [
            models.Index(fields=["company", "active"], name="hr_job_company_active_idx"),
            models.Index(fields=["department", "active"], name="hr_job_departm_active_idx"),
            models.Index(fields=["name"], name="hr_job_name_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["name", "company", "department"],
                name="uniq_job_name_company_department",
            ),
            models.CheckConstraint(
                name="chk_no_of_recruitment_nonneg",
                check=models.Q(no_of_recruitment__gte=0),
            ),
        ]
        ordering = ("sequence",)

    def __str__(self):
        return self.name


# ------------------------------------------------------------
# EmployeeCategory — وسم/فئة موظف (غير هرمي)
# ------------------------------------------------------------
class EmployeeCategory(TimeStampedMixin, UserStampedMixin, models.Model):
    name = models.CharField(max_length=128, unique=True)
    color = models.PositiveSmallIntegerField(default=1)

    class Meta:
        db_table = "hr_employee_category"

    def __str__(self):
        return self.name


# ------------------------------------------------------------
# Employee — الموظف (مع ACL + Company scope)
# ------------------------------------------------------------
class Employee(AccessControlledMixin, CompanyOwnedMixin, ActivableMixin, TimeStampedMixin, UserStampedMixin, models.Model):
    """
    Odoo-like hr.employee
    - company scope عبر CompanyOwnedMixin
    - ACL على مستوى السجل عبر AccessControlledMixin (سلوك "خاص داخل الشركة" + مشاركة)
    - work_contact: بطاقة Partner وظيفية إجبارية (تُدار بالإشارات)
    - إن كان مرتبطًا بمستخدم: work_contact = partner الخاص بالمستخدم
    """
    company = models.ForeignKey(
        "base.Company",
        on_delete=models.PROTECT,
        related_name="employees",
    )

    name = models.CharField(max_length=255, db_index=True)

    user = models.ForeignKey(
        "base.User",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="employees",
    )

    department = models.ForeignKey(
        "hr.Department",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="members",
    )

    job = models.ForeignKey(
        "hr.Job",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="employee_set",
    )

    manager = models.ForeignKey(
        "self",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="managed_employees",
    )

    coach = models.ForeignKey(
        "self",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="coachees",
    )

    # جهة الاتصال الوظيفية (Partner تابع للشركة) — سيُملأ تلقائيًا
    work_contact = models.ForeignKey(
        "base.Partner",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="employee_work_contact",
        editable=False,  # ← لا يظهر في أي ModelForm (يوضَّح فقط قراءةً)
        help_text="Assigned automatically from User partner or created under company.",
    )

    # العلاقات التي يجب أن تتبع شركة الموظف
    company_dependent_relations = (
        "department",
        "job",
        "manager",
        "coach",
        "work_location",
        "work_contact",
    )

    # بيانات خاصة/شخصية
    private_phone = models.CharField(max_length=64, blank=True)
    private_email = models.EmailField(blank=True)
    birthday = models.DateField(null=True, blank=True)
    place_of_birth = models.CharField(max_length=255, blank=True)
    birthday_public_display_string = models.CharField(max_length=64, blank=True)
    coach_id_cache = models.CharField(max_length=255, blank=True)

    # للطوارئ
    emergency_contact = models.CharField(max_length=255, blank=True)
    emergency_phone = models.CharField(max_length=64, blank=True)

    # تعليم/إقامة
    certificate = models.CharField(max_length=64, blank=True)
    study_field = models.CharField(max_length=128, blank=True)
    study_school = models.CharField(max_length=128, blank=True)

    marital_status = models.CharField(
        max_length=32, blank=True,
        choices=[("single", "Single"), ("married", "Married"), ("divorced", "Divorced"), ("widow", "Widow")],
    )
    gender = models.CharField(
        max_length=16, blank=True,
        choices=[("male", "Male"), ("female", "Female")],
    )
    children = models.PositiveIntegerField(default=0, help_text="Number of children")

    identification_id = models.CharField(max_length=64, blank=True, help_text="National ID / Identification")
    passport_id = models.CharField(max_length=64, blank=True, help_text="Passport number")
    bank_account = models.CharField(max_length=128, blank=True, help_text="Bank account details")
    car = models.CharField(max_length=128, blank=True, help_text="Vehicle information (if applicable)")

    work_location = models.ForeignKey(
        "hr.WorkLocation",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="employees",
    )

    categories = models.ManyToManyField("hr.EmployeeCategory", blank=True, related_name="employees")

    barcode = models.CharField(max_length=64, blank=True, null=True)
    pin = models.CharField(max_length=32, blank=True)

    class Meta:
        db_table = "hr_employee"
        indexes = [
            models.Index(fields=["company", "active"], name="hr_employee_company_active_idx"),
            models.Index(fields=["name"], name="hr_employee_name_idx"),
            models.Index(fields=["active"], name="hr_employee_active_idx"),
            models.Index(fields=["department"], name="hr_employee_departm_idx"),
            models.Index(fields=["company", "user"], name="hr_emp_comp_user_idx"),
            models.Index(fields=["company", "work_contact"], name="hr_emp_comp_workct_idx"),
            models.Index(fields=["company", "pin"], name="hr_emp_comp_pin_idx"),
            models.Index(fields=["company", "barcode"], name="hr_emp_comp_barcode_idx"),
        ]
        constraints = [
            # barcode فريد على مستوى النظام كله (مطابق لأودو) — نسمح بتكرار NULL و ""
            models.UniqueConstraint(
                fields=["barcode"],
                name="uniq_employee_barcode",
                condition=models.Q(barcode__isnull=False) & ~models.Q(barcode=""),
            ),
            models.CheckConstraint(
                name="employee_manager_not_self",
                check=~models.Q(pk=models.F("manager")),
            ),
            models.CheckConstraint(
                name="employee_coach_not_self",
                check=~models.Q(pk=models.F("coach")),
            ),
            # PIN فريد داخل الشركة — نسمح بتكرار NULL و ""
            models.UniqueConstraint(
                fields=["company", "pin"],
                name="uniq_employee_pin_per_company",
                condition=models.Q(pin__isnull=False) & ~models.Q(pin=""),
            ),
            # مستخدم واحد ↔ موظف واحد على مستوى النظام كله (الأقوى والأقرب لمنطق Odoo)
            models.UniqueConstraint(
                fields=["user"],
                name="hr_employee_user_uniq",
                condition=models.Q(user__isnull=False),
            ),
            models.UniqueConstraint(
                fields=["work_contact"],
                name="hr_employee_unique_work_contact",
                condition=models.Q(work_contact__isnull=False),
            ),
        ]
        permissions = [
            ("approve_employee", "Can approve employee record"),
            ("view_private_fields", "Can view employee private fields"),
        ]

    # --------- خصائص مُساعدة ----------
    @property
    def hr_presence_state(self):
        return "archive" if not self.active else "present"

    @property
    def hr_icon_display(self):
        return "fa-user"

    @property
    def show_hr_icon_display(self):
        return self.active

    # --------- تحقق ----------
    def clean(self):
        super().clean()

        # ------------------------------------------------------------
        # 1) علاقات يجب أن تتبع نفس الشركة (Odoo-like company scope)
        # ------------------------------------------------------------
        for fname in ("department", "job", "work_location", "work_contact"):
            rel = getattr(self, fname, None)
            if rel and getattr(rel, "company_id", None) and rel.company_id != self.company_id:
                raise ValidationError({fname: "Must match employee company."})

        if self.manager and getattr(self.manager, "company_id", None) != self.company_id:
            raise ValidationError({"manager": "Manager must match employee company."})

        if self.coach and getattr(self.coach, "company_id", None) != self.company_id:
            raise ValidationError({"coach": "Coach must match employee company."})

        # ------------------------------------------------------------
        # 2) منع self-reference (لا يمكن أن يكون الموظف مدير/مدرّب نفسه)
        # ------------------------------------------------------------
        if self.pk:
            if self.manager_id and self.manager_id == self.pk:
                raise ValidationError({"manager": "Employee cannot be their own manager."})
            if self.coach_id and self.coach_id == self.pk:
                raise ValidationError({"coach": "Employee cannot be their own coach."})

        # ------------------------------------------------------------
        # 3) Work contact sanity (جهة العمل يجب أن تتبع نفس الشركة)
        # ------------------------------------------------------------
        if self.work_contact_id:
            wc = self.work_contact
            # company must match employee company
            if getattr(wc, "company_id", None) != self.company_id:
                raise ValidationError({"work_contact": "Work contact must belong to the employee company."})
            # if parent has company, it must be the same employee company
            parent_company_id = getattr(getattr(wc, "parent", None), "company_id", None)
            if parent_company_id and parent_company_id != self.company_id:
                raise ValidationError({"work_contact": "Work contact must be a child of the employee company partner."})

        # ------------------------------------------------------------
        # 4) User/company consistency (مطابق لمنطق Odoo)
        #    - شركة المستخدم الرئيسية = شركة الموظف
        #    - شركة الموظف ضمن شركات المستخدم المسموح بها
        # ------------------------------------------------------------
        if self.user_id and self.company_id:
            u = self.user
            # main company must match
            if getattr(u, "company_id", None) != self.company_id:
                raise ValidationError({"user": "User's main company must match the employee company."})
            # allowed companies must include employee company
            if hasattr(u, "companies") and not u.companies.filter(pk=self.company_id).exists():
                raise ValidationError({"user": "Add this company to the user's allowed companies first."})

        # ------------------------------------------------------------
        # 5) منع تكرار نفس (user, company) مسبقًا (mirror DB constraint)
        # ------------------------------------------------------------
        if self.user_id and self.company_id:
            qs = type(self).objects.filter(company_id=self.company_id, user_id=self.user_id)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError({"user": "This user already has an employee in this company."})

        # ------------------------------------------------------------
        # 6) تنظيف الباركود (تنميط بسيط)
        # ------------------------------------------------------------
        if self.barcode is not None:
            self.barcode = self.barcode.strip()
            if self.barcode == "":
                self.barcode = None

    # --------- حفظ ----------
    def save(self, *args, **kwargs):
        # عرض تاريخ الميلاد (للاستخدامات البسيطة)
        if self.birthday:
            self.birthday_public_display_string = self.birthday.strftime("%d %B")

        # كاش للمدرّب
        self.coach_id_cache = str(self.coach_id) if self.coach_id else ""



        # Normalize للباركود
        if self.barcode == "":
            self.barcode = None

        # احتفظ بالقديم قبل الحفظ الفعلي (قد تكون _old_work_contact_id ملتقطة من signal، وإن لم تكن نلتقطها هنا)
        old_wc_id = getattr(self, "_old_work_contact_id", None)
        if self.pk and old_wc_id is None:
            try:
                old_wc_id = type(self).objects.only("work_contact_id").get(pk=self.pk).work_contact_id
            except type(self).DoesNotExist:
                old_wc_id = None

        super().save(*args, **kwargs)

        # بعد الحفظ: فعّل العلم على الشريك الحالي، وانزعه عن القديم إذا لم يعد مستخدماً
        from django.apps import apps
        Partner = apps.get_model("base", "Partner")
        Emp = type(self)

        if self.work_contact_id:
            Partner.objects.filter(pk=self.work_contact_id, employee=False).update(employee=True)

        if old_wc_id and old_wc_id != self.work_contact_id:
            still_used = Emp.objects.filter(work_contact_id=old_wc_id).exists()
            if not still_used:
                Partner.objects.filter(pk=old_wc_id, employee=True).update(employee=False)

    # --------- مساعدات ----------
    @property
    def current_skills(self):
        from skills.models import EmployeeSkill
        return EmployeeSkill.current_for_employee(self.id)

    def __str__(self):
        return self.name

