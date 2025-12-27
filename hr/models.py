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
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from django.urls import reverse

# مكسنات وبُنى أساسية من تطبيق base
from base.models import (
    CompanyOwnedMixin,  # يضمن company + فحوص التوافق
    ActivableMixin,  # يحوي active=BooleanField
    TimeStampedMixin,  # created_at / updated_at
    UserStampedMixin, CompanyScopeManager,  # created_by / updated_by
)

# ACL (صلاحيات كائنية) — نطبّقها على Employee تحديدًا
from base.acl import AccessControlledMixin, ACLManager, ACLQuerySet


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
# NOTE:
# HR core models (Employee, Department, Job) are designed to be ARCHIVED
# using `active=False` instead of being deleted.
# Deletion is intentionally restricted via on_delete=PROTECT
# to preserve historical integrity and references.

# ------------------------------------------------------------
class Department(AccessControlledMixin,CompanyOwnedMixin, ActivableMixin, TimeStampedMixin, UserStampedMixin, models.Model):
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

    # ---------------------------------------------------------
    #  Department level (division / department / section / team)
    # ---------------------------------------------------------
    @property
    def level(self):
        """
        Hierarchical level used for UI rendering.
        """
        depth = self.parent_path.count("/") - 1 if self.parent_path else 0

        if depth <= 0:
            return "division"
        elif depth == 1:
            return "department"
        elif depth == 2:
            return "section"
        else:
            return "team"

    objects = CompanyScopeManager()
    acl_objects = ACLManager()

    class Meta:
        db_table = "hr_department"
        indexes = [
            models.Index(fields=["company", "active"], name="hr_departme_company_active_idx"),
            models.Index(fields=["company", "parent"], name="hr_departme_company_parent_idx"),
            models.Index(fields=["parent_path"], name="hr_departme_parent_path_idx"),
            models.Index(fields=["complete_name"], name="hr_departme_complete_name_idx"),
        ]
        ordering = ("name",)
        constraints = [
            # 1) الأقسام الجذرية (parent = NULL): الاسم يجب أن يكون فريدًا داخل الشركة
            models.UniqueConstraint(
                fields=["company", "name"],
                condition=Q(parent__isnull=True),
                name="uniq_department_root_per_company_name",
            ),

            # 2) الأقسام غير الجذرية (parent != NULL): الاسم فريد داخل نفس الأب + نفس الشركة
            models.UniqueConstraint(
                fields=["company", "parent", "name"],
                condition=Q(parent__isnull=False),
                name="uniq_department_per_company_parent_name",
            ),
        ]

    # ---------- خواص محسوبة ----------
    @property
    def member_count(self) -> int:
        """عدد الموظفين النشِطين في القسم (سلوك Odoo)."""
        return self.members.filter(active=True).count()

    @property
    def employee_count(self):
        """Count all active employees inside this department subtree (including self) without double counting."""
        return Employee.objects.filter(
            active=True,
            company_id=self.company_id,
            department__parent_path__startswith=self.parent_path
        ).count()

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

    # ---------------------------------------------------------
    #  Tree helpers (used by views + templates)
    # ---------------------------------------------------------

    @property
    def children_list(self):
        """Return active direct children."""
        return self.children.filter(active=True).order_by("name")

    def get_descendants(self):
        """Return all departments under this department."""
        return Department.objects.filter(
            parent_path__startswith=self.parent_path,
            active=True,
            company_id=self.company_id
        ).exclude(pk=self.pk)

    def get_ancestors(self):
        """Return all parents up to root (excluding self)."""
        ids = [int(x) for x in self.parent_path.split("/") if x]
        return Department.objects.filter(pk__in=ids).exclude(pk=self.pk).order_by("parent_path")

    # ---------- lifecycle ----------
    def save(self, *args, **kwargs):
        """
        Lifecycle save:
        1) Save first to ensure PK exists
        2) Recompute own lineage fields (complete_name / parent_path)
        3) Persist lineage fields efficiently
        4) Recompute subtree only when structural fields change
        """

        # المدير السابق قبل الحفظ (للمقارنة فقط — توثيقي)
        prev_parent_id = None
        if self.pk:
            prev_parent_id = type(self).objects.only("parent_id").filter(pk=self.pk) \
                .values_list("parent_id", flat=True).first()

        # 1) احفظ للحصول على PK أو تحديث الحقول الأساسية
        super().save(*args, **kwargs)

        # 2) أعد حساب حقول السلسلة للقسم الحالي
        self._recompute_lineage_fields()
        super().save(update_fields=["complete_name", "parent_path"])

        # 3) حدّث الفروع فقط إذا تغيّر الأب (تحسين أداء)
        if prev_parent_id != self.parent_id:
            self._recompute_subtree()

        # 4) لا يوجد أي اشتقاق تلقائي للمدير على الموظفين (Odoo-like behavior)

    # ---------- Validation ----------
    def clean(self):
        """
        Business validations for Department (Odoo-like).

        Guarantees:
        - No DB constraint errors reach the user
        - All validation errors are user-friendly
        - No interference with CompanyScope / ACL managers
        """

        super().clean()

        # استخدم manager غير مقيّد لضمان رؤية كل السجلات
        BaseMgr = type(self)._base_manager

        # --------------------------------------------------
        # 1) Parent department must belong to the same company
        # --------------------------------------------------
        if self.parent and self.parent.company_id != self.company_id:
            raise ValidationError({
                "parent": "Parent department must belong to the same company."
            })

        # --------------------------------------------------
        # 2) Prevent self-parent and cyclic hierarchy
        # --------------------------------------------------
        # Direct self-parent
        if self.parent and self.pk and self.parent_id == self.pk:
            raise ValidationError({
                "parent": "A department cannot be parent of itself."
            })

        # Cyclic hierarchy (walk up)
        node = self.parent
        while node:
            if node.pk == self.pk:
                raise ValidationError({
                    "parent": "Cyclic department hierarchy is not allowed."
                })
            node = node.parent

        # --------------------------------------------------
        # 3) Prevent duplicate ROOT departments (company + name)
        # --------------------------------------------------
        if self.parent is None and self.company_id and self.name:
            qs = BaseMgr.filter(
                company_id=self.company_id,
                parent__isnull=True,
                name__iexact=self.name.strip(),
            )

            if self.pk:
                qs = qs.exclude(pk=self.pk)

            if qs.exists():
                raise ValidationError({
                    "name": (
                        "A root department with this name already exists in this company. "
                        "Please choose a different name or assign a parent department."
                    )
                })

        # --------------------------------------------------
        # 4) Prevent duplicate CHILD departments
        #    (same company + same parent + same name)
        # --------------------------------------------------
        if self.parent_id and self.company_id and self.name:
            qs = BaseMgr.filter(
                company_id=self.company_id,
                parent_id=self.parent_id,
                name__iexact=self.name.strip(),
            )

            if self.pk:
                qs = qs.exclude(pk=self.pk)

            if qs.exists():
                raise ValidationError({
                    "name": (
                        "A department with this name already exists under the selected parent."
                    )
                })

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

    objects = CompanyScopeManager()
    acl_objects = ACLQuerySet.as_manager()

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
# WorkShift / WorkShiftRule (Odoo-like resource.calendar)
# ------------------------------------------------------------

class WorkShift(CompanyOwnedMixin, ActivableMixin, TimeStampedMixin, UserStampedMixin, models.Model):
    """
    تقويم دوام (Shift/Calendar) على مستوى الشركة فقط (Company-level).
    لا يوجد ربط على مستوى الأقسام.
    """
    name = models.CharField(max_length=255)
    company = models.ForeignKey(
        "base.Company",
        on_delete=models.PROTECT,
        related_name="work_shifts",
    )

    code = models.CharField(max_length=32, blank=True)
    timezone = models.CharField(
        max_length=64,
        default="Asia/Baghdad",
        help_text="IANA time zone (e.g., Asia/Baghdad)",
    )
    hours_per_day = models.DecimalField(max_digits=5, decimal_places=2, default=8)  # مرجع عام فقط
    note = models.TextField(blank=True)

    def clean(self):
        super().clean()
        # ساعات اليوم يجب أن تكون ضمن (0,24]
        if self.hours_per_day is not None and (self.hours_per_day <= 0 or self.hours_per_day > 24):
            raise ValidationError({"hours_per_day": "Hours per day must be within (0, 24]."})

    def __str__(self):
        comp = f"{self.company}" if getattr(self, "company", None) else "Company"
        return f"{self.name} ({comp})"

    class Meta:
        db_table = "hr_work_shift"
        indexes = [
            models.Index(fields=["company", "active"], name="hr_ws_company_active_idx"),
            models.Index(fields=["company", "name"], name="hr_ws_comp_name_idx"),
        ]
        constraints = [
            # فريد داخل الشركة
            models.UniqueConstraint(
                fields=["company", "name"],
                name="uniq_ws_company_name",
            ),
        ]
        ordering = ("company", "name")

class WorkShiftRule(TimeStampedMixin, UserStampedMixin, models.Model):
    """
    قاعدة يومية واحدة لكل يوم ضمن الشفت (Mon..Sun).
    دعم "الشفت العابر لمنتصف الليل" عبر spans_next_day:
      - مثال: start=16:30, end=01:00, spans_next_day=True
    """
    WEEKDAY = [(0,"Mon"),(1,"Tue"),(2,"Wed"),(3,"Thu"),(4,"Fri"),(5,"Sat"),(6,"Sun")]

    shift = models.ForeignKey("hr.WorkShift", on_delete=models.CASCADE, related_name="rules")
    weekday = models.PositiveSmallIntegerField(choices=WEEKDAY)
    start_time = models.TimeField()
    end_time = models.TimeField()
    break_minutes = models.PositiveSmallIntegerField(default=0)
    spans_next_day = models.BooleanField(default=False)  # يدعم عبور منتصف الليل

    def clean(self):
        super().clean()
        if self.break_minutes < 0 or self.break_minutes > 600:
            raise ValidationError({"break_minutes": "Break minutes must be between 0 and 600."})

        if not self.spans_next_day:
            # الحالة العادية: يجب أن يكون end > start
            if self.start_time >= self.end_time:
                raise ValidationError({"end_time": "End time must be greater than start time (same day)."})
        else:
            # العابر لمنتصف الليل: end_time قد يكون <= start_time، لكن لا يمكن أن يساوِيه
            if self.start_time == self.end_time:
                raise ValidationError({"end_time": "Overnight rule cannot have identical start/end times."})

        if self.net_minutes <= 0:
            raise ValidationError({"end_time": "Net working minutes must be positive."})

    @property
    def net_minutes(self) -> int:
        """المدة الصافية لهذا اليوم (بالدقائق) = (المدة الكاملة - الاستراحة)، مع دعم overnight."""
        s = self.start_time
        e = self.end_time
        if s is None or e is None:
            return 0

        s_tot = s.hour*60 + s.minute
        e_tot = e.hour*60 + e.minute

        if not self.spans_next_day:
            total = e_tot - s_tot
        else:
            # مثال 16:30 → 01:00: المدة = (24*60 - s) + e
            total = (24*60 - s_tot) + e_tot

        return max(0, total - (self.break_minutes or 0))

    def __str__(self):
        tag = "↦+1d" if self.spans_next_day else ""
        return f"{self.shift.name} · {self.get_weekday_display()} {self.start_time}-{self.end_time}{tag}"

    class Meta:
        db_table = "hr_work_shift_rule"
        constraints = [
            # قاعدة واحدة فقط لكل يوم داخل الشفت (بسيط وواضح)
            models.UniqueConstraint(fields=["shift", "weekday"], name="uniq_rule_weekday_per_shift"),
        ]
        ordering = ("shift", "weekday", "start_time")


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

    objects = CompanyScopeManager()
    acl_objects = ACLQuerySet.as_manager()

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

    @property
    def employee_count(self):
        return self.employee_set.filter(active=True).count()

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
# EmployeeSchedule / EmployeeDayOff (Odoo-like assignments & leaves)
# ------------------------------------------------------------

class EmployeeSchedule(ActivableMixin, TimeStampedMixin, UserStampedMixin, models.Model):
    """
    يربط الموظف بشفت ضمن فترة (من/إلى). يمنع التداخل التاريخي ويُلزم تطابق الشركة.
    الآن يتضمن أيضًا العطلة الأسبوعية الثابتة (داخل نفس السجل) عبر weekly_off_mask.
    """
    # ثوابت البِتّات لأيام الأسبوع (Mon..Sun)
    MON = 1 << 0  # 1
    TUE = 1 << 1  # 2
    WED = 1 << 2  # 4
    THU = 1 << 3  # 8
    FRI = 1 << 4  # 16
    SAT = 1 << 5  # 32
    SUN = 1 << 6  # 64
    WEEKDAY_CHOICES = [(0,"Mon"),(1,"Tue"),(2,"Wed"),(3,"Thu"),(4,"Fri"),(5,"Sat"),(6,"Sun")]
    WEEKDAY_TO_BIT = {0: MON, 1: TUE, 2: WED, 3: THU, 4: FRI, 5: SAT, 6: SUN}

    employee   = models.ForeignKey("hr.Employee", on_delete=models.CASCADE, related_name="schedules")
    shift      = models.ForeignKey("hr.WorkShift", on_delete=models.PROTECT, related_name="employee_schedules")
    date_from  = models.DateField()
    date_to    = models.DateField(null=True, blank=True)  # فترة مفتوحة ممكنة

    # [NEW] أيام العطلة الأسبوعية لهذه الفترة (bitmask)
    weekly_off_mask = models.PositiveSmallIntegerField(default=0, help_text="Weekly off days as bitmask (Mon..Sun)")

    # ---------- أدوات مساعدة للـ mask ----------
    @classmethod
    def mask_from_weekday_list(cls, weekday_list):
        mask = 0
        for wd in (weekday_list or []):
            mask |= cls.WEEKDAY_TO_BIT.get(int(wd), 0)
        return mask

    @classmethod
    def weekday_list_from_mask(cls, mask):
        out = []
        for wd, bit in cls.WEEKDAY_TO_BIT.items():
            if mask & bit:
                out.append(wd)
        return out

    @staticmethod
    def _bitcount(n: int) -> int:
        return bin(n).count("1")

    def clean(self):
        super().clean()

        # 1) إلزام تطابق الشركة بين الموظف والشفت
        if self.employee_id and self.shift_id:
            if self.employee.company_id != self.shift.company_id:
                raise ValidationError({"shift": "Shift must belong to the same company as the employee."})

        # 2) إلزام date_from
        if not self.date_from:
            raise ValidationError({"date_from": "This field is required."})

        # 3) منع التداخل: يُتحقق منه على مستوى Inline FormSet في الأدمن لتجنّب القراءة من DB قبل الحفظ.

        # 4) تحقق العطلة الأسبوعية: لازم يختار 1 أو 2 أيام (حسب سيناريو شركتك)
        if self.weekly_off_mask == 0:
            # خطأ عام لأن الفورم يعرض weekly_off_days (وليس weekly_off_mask)
            raise ValidationError("Select at least one weekly off day.")
        off_count = self._bitcount(self.weekly_off_mask)
        if off_count not in (1, 2):
            # اجعل الخطأ عامًا كذلك كي لا يرتبط بحقل غير معروض
            raise ValidationError("Weekly off must be 1 day (6-day work) or 2 days (5-day work).")

    def __str__(self):
        days = ",".join(dict(self.WEEKDAY_CHOICES)[wd] for wd in self.weekday_list_from_mask(self.weekly_off_mask))
        return f"{self.employee} · {self.shift} [{self.date_from} → {self.date_to or '...'}] · OFF({days})"

    class Meta:
        db_table = "hr_employee_schedule"
        indexes = [
            models.Index(fields=["employee", "active"], name="hr_es_emp_active_idx"),
            models.Index(fields=["employee", "-date_from"], name="hr_es_emp_from_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["employee"],
                name="uniq_open_schedule_per_employee",
                condition=models.Q(active=True, date_to__isnull=True),
            ),
        ]
        ordering = ("-date_from",)


class EmployeeWeeklyOffPeriod(ActivableMixin, TimeStampedMixin, UserStampedMixin, models.Model):
    """
    العطل الأسبوعية الثابتة للموظف على شكل "سجل واحد" يُحوي عدة أيام عبر checkboxes.
    تُحفظ داخليًا كـ Bitmask داخل days_mask.
    - دعم الفترات التاريخية (date_from/date_to)، مع منع التداخل إن كان هناك اشتراك بأيام.
    - مثال: موظف يعمل 5 أيام → يختار يومين (Fri, Sat) لسجله الحالي؛ لاحقًا يُغلق هذا السجل ويفتح سجلًا آخر أيام (Sun, Mon).
    - موظف يعمل 6 أيام → يختار يومًا واحدًا فقط.
    """

    # ثوابت البتّات للأيام (Sun..Sat أو Mon..Sun حسب تفضيلك؛ هنا Mon..Sun لأتساق قواعد الشفت)
    MON = 1 << 0  # 1
    TUE = 1 << 1  # 2
    WED = 1 << 2  # 4
    THU = 1 << 3  # 8
    FRI = 1 << 4  # 16
    SAT = 1 << 5  # 32
    SUN = 1 << 6  # 64

    WEEKDAY_CHOICES = [
        (0, "Mon"),
        (1, "Tue"),
        (2, "Wed"),
        (3, "Thu"),
        (4, "Fri"),
        (5, "Sat"),
        (6, "Sun"),
    ]
    WEEKDAY_TO_BIT = {
        0: MON, 1: TUE, 2: WED, 3: THU, 4: FRI, 5: SAT, 6: SUN
    }

    employee = models.ForeignKey("hr.Employee", on_delete=models.CASCADE, related_name="weekly_off_periods")
    date_from = models.DateField()
    date_to = models.DateField(null=True, blank=True)  # فترة مفتوحة ممكنة
    days_mask = models.PositiveSmallIntegerField(default=0, help_text="Bitmask of weekly off days (Mon..Sun)")

    # ---------- أدوات مساعدة للتعامل مع الـ mask ----------
    @classmethod
    def to_mask(cls, weekday_list):
        """من قائمة أرقام الأيام → bitmask."""
        mask = 0
        for wd in (weekday_list or []):
            mask |= cls.WEEKDAY_TO_BIT.get(int(wd), 0)
        return mask

    @classmethod
    def from_mask(cls, mask):
        """من bitmask → قائمة أرقام الأيام المختارة."""
        out = []
        for wd, bit in cls.WEEKDAY_TO_BIT.items():
            if mask & bit:
                out.append(wd)
        return out

    def has_overlap_on_any_day(self, other_mask: int) -> bool:
        """هل يوجد أي يوم مشترك بين this.days_mask و other_mask؟"""
        return (self.days_mask & other_mask) != 0

    # ---------- تحقق صحة ----------
    def clean(self):
        super().clean()
        # يجب اختيار يوم/أيام على الأقل
        if not self.days_mask:
            raise ValidationError({"days_mask": "Select at least one weekly off day."})

        # منع التداخل: نفس الموظف، أي تقاطع في الأيام + تداخل زمني
        if self.employee_id and self.date_from is not None:
            qs = type(self).objects.filter(employee_id=self.employee_id, active=True)
            if self.pk:
                qs = qs.exclude(pk=self.pk)

            df, dt = self.date_from, self.date_to

            # فترة المرشح (df..dt) تتداخل مع فترة أخرى؟
            if dt:
                overlap_time = (
                    (models.Q(date_to__isnull=True) | models.Q(date_to__gte=df)) &
                    models.Q(date_from__lte=dt)
                )
            else:
                overlap_time = (models.Q(date_to__isnull=True) | models.Q(date_to__gte=df))

            # فلترة أولية على التداخل الزمني
            qs = qs.filter(overlap_time)

            # فحص التقاطع في الأيام
            for other in qs.only("days_mask"):
                if (self.days_mask & other.days_mask) != 0:
                    raise ValidationError("Overlapping weekly-off periods on intersecting weekdays are not allowed.")

    def __str__(self):
        day_labels = [dict(self.WEEKDAY_CHOICES)[wd] for wd in self.from_mask(self.days_mask)]
        label = ",".join(day_labels) or "—"
        return f"{self.employee} · OFF [{label}] [{self.date_from} → {self.date_to or '...'}]"

    class Meta:
        db_table = "hr_employee_weekly_off_period"
        indexes = [
            models.Index(fields=["employee", "-date_from"], name="hr_ewop_emp_from_idx"),
        ]
        constraints = [
            # يمكن أن يكون هناك أكثر من سجل مفتوح بشرط ألا تتقاطع الأيام.
            # (المنع الفعلي للتقاطع ننجزه في clean() لأن DB constraints لا تفهم bitmask بسهولة)
        ]
        ordering = ("employee", "-date_from")


class Employee(
    CompanyOwnedMixin,
    ActivableMixin,
    TimeStampedMixin,
    UserStampedMixin,
    models.Model,
):
    """
    Odoo-like hr.employee (ACL REMOVED).

    - Company scoped
    - Archived via active=False
    - No record-level permissions
    """

    objects = CompanyScopeManager()

    name = models.CharField(max_length=255, db_index=True)

    user = models.OneToOneField(
        "base.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="employee",
    )

    department = models.ForeignKey(
        "hr.Department",
        on_delete=models.PROTECT,
        related_name="members",
    )

    job = models.ForeignKey(
        "hr.Job",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="employees",
    )

    manager = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="managed_employees",
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
        editable=False,
    )

    private_phone = models.CharField(max_length=64, blank=True)
    private_email = models.EmailField(blank=True)
    birthday = models.DateField(null=True, blank=True)
    place_of_birth = models.CharField(max_length=255, blank=True)

    emergency_contact = models.CharField(max_length=255, blank=True)
    emergency_phone = models.CharField(max_length=64, blank=True)

    certificate = models.CharField(max_length=64, blank=True)
    study_field = models.CharField(max_length=128, blank=True)
    study_school = models.CharField(max_length=128, blank=True)

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

    children = models.PositiveIntegerField(default=0)

    identification_id = models.CharField(max_length=64, blank=True)
    passport_id = models.CharField(max_length=64, blank=True)
    bank_account = models.CharField(max_length=128, blank=True)
    car = models.CharField(max_length=128, blank=True)

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
        ordering = ["name"]
        indexes = [
            models.Index(fields=["company", "active"]),
            models.Index(fields=["name"]),
            models.Index(fields=["department"]),
        ]

    # ------------------------------------------------------------
    # Validation (unchanged – business rules only)
    # ------------------------------------------------------------
    def clean(self):
        super().clean()

        if self.manager_id and self.manager_id == self.pk:
            raise ValidationError({"manager": "Employee cannot be their own manager."})

        node = self.manager
        while node:
            if node.pk == self.pk:
                raise ValidationError({"manager": "Cyclic managerial hierarchy is not allowed."})
            node = node.manager

        if self.barcode is not None:
            self.barcode = self.barcode.strip() or None

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    # ------------------------------------------------------------
    # URLs
    # ------------------------------------------------------------
    def get_absolute_url(self):
        return reverse("hr:employee_detail", kwargs={"pk": self.pk})

    def get_edit_url(self):
        return reverse("hr:employee_edit", kwargs={"pk": self.pk})

    def __str__(self):
        return self.name



# -------------------------------------------------------------
# Company-wide tree builder
# -------------------------------------------------------------
def get_root_departments(company_id):
    """Return root divisions for the company."""
    if not company_id:
        return Department.objects.none()

    return Department.objects.filter(
        company_id=company_id,
        parent__isnull=True,
        active=True
    ).order_by("name")


def build_department_tree(nodes, depth=0):
    """
    Build a UI-ready department tree.
    Each node carries presentation metadata.
    """

    tree = []

    for node in nodes:
        children = build_department_tree(node.children_list, depth + 1)

        tree.append({
            "id": node.id,
            "obj": node,
            "depth": depth,                     # مهم جدًا للـ UI
            "level": node.level,                # division / department / section / team
            "has_children": bool(children),
            "children": children,
        })

    return tree

