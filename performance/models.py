# performance/models.py
"""
نظام الأداء (Performance) — متوافق مع روح Odoo داخل نطاق HR:
- Objectives (أهداف) + KPIs + Tasks
- Assignments (إسناد الأهداف للأقسام/الموظفين) + materialized participants
- Evaluations (نماذج تقييم نهاية الفترة) + قوالب/معاملات + نتائج المعاملات
"""

from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.utils import timezone

# مكسينات أساسية موحّدة في المشروع
from base.models import (
    CompanyOwnedMixin,  # يضيف company + company اتساق
    ActivableMixin,  # active
    TimeStampedMixin,  # created_at / updated_at
    UserStampedMixin, CompanyScopeManager,  # created_by / updated_by
)


# ------------------------------------------------------------
# Task
# ------------------------------------------------------------

class TaskStatus(ActivableMixin, TimeStampedMixin, UserStampedMixin, models.Model):
    """
    حالة المهمة: ديناميكية يتم إدارتها من الـ Admin.
    أمثلة: To Do, In Progress, Blocked, Done, Cancelled.
    """
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=32, unique=True, db_index=True)
    sequence = models.PositiveIntegerField(default=10)

    is_closed = models.BooleanField(default=False, help_text="Does this status close the task?")
    is_blocking = models.BooleanField(default=False, help_text="Is this a blocking state?")

    class Meta:
        db_table = "perf_task_status"
        ordering = ("sequence", "name")
        indexes = [models.Index(fields=["active", "code"])]

    def __str__(self):
        return self.name

class TaskType(ActivableMixin, TimeStampedMixin, UserStampedMixin, models.Model):
    """
    نوع المهمة: Planned, Ad-hoc, BAU, Incident Review, etc.
    """
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=64, unique=True, db_index=True)
    description = models.TextField(blank=True)

    class Meta:
        db_table = "perf_task_type"
        ordering = ("name",)
        indexes = [models.Index(fields=["active", "code"])]

    def __str__(self):
        return self.name

class TaskCategory(ActivableMixin, TimeStampedMixin, UserStampedMixin, models.Model):
    """
    تصنيف المهمة: Quality, Operational, Development, Training, etc.
    """
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=64, unique=True, db_index=True)
    description = models.TextField(blank=True)

    class Meta:
        db_table = "perf_task_category"
        ordering = ("name",)
        indexes = [models.Index(fields=["active", "code"])]

    def __str__(self):
        return self.name

class TaskSLAPolicy(CompanyOwnedMixin, ActivableMixin, TimeStampedMixin, UserStampedMixin, models.Model):
    """
    سياسة SLA لحساب timeliness / delay penalties / blocked handling.
    """
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=64, unique=True)
    description = models.TextField(blank=True)

    # thresholds
    on_time_pct = models.PositiveIntegerField(default=100)
    mild_delay_pct = models.PositiveIntegerField(default=80)
    severe_delay_pct = models.PositiveIntegerField(default=50)

    allow_blocked_external_no_penalty = models.BooleanField(default=True)

    class Meta:
        db_table = "perf_task_sla_policy"
        ordering = ("company", "name")
        indexes = [models.Index(fields=["company","active"])]

    def __str__(self):
        return self.name

class TaskProgressPolicy(ActivableMixin, TimeStampedMixin, UserStampedMixin, models.Model):
    """
    قواعد حساب progress للمهمة:
    - by status
    - by subtasks
    - by time spent
    - by manual rules
    """
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=64, unique=True)
    description = models.TextField(blank=True)

    use_subtasks = models.BooleanField(default=False)
    use_time_ratio = models.BooleanField(default=False)
    use_status_mapping = models.BooleanField(default=True)

    class Meta:
        db_table = "perf_task_progress_policy"
        ordering = ("name",)

# ------------------------------------------------------------
# TaskRecurringDefinition
# ------------------------------------------------------------
class TaskRecurringDefinition(
    
    CompanyOwnedMixin,
    TimeStampedMixin,
    UserStampedMixin,
    ActivableMixin,
    models.Model
):
    """
    تعريف المهام الدورية (يُنشأ يدوياً من الـ Admin ثم تُستخدم خدمة RecurringTaskService لتوليد المهام).
    """

    SCHEDULE_KIND = [
        ("monthly", "Monthly"),
        ("weekly", "Weekly"),
        ("custom", "Custom Period"),
    ]

    company = models.ForeignKey(
        "base.Company",
        on_delete=models.PROTECT,
        related_name="recurring_task_definitions"
    )

    name = models.CharField(max_length=255)
    code = models.CharField(max_length=64, blank=True, db_index=True)

    schedule_kind = models.CharField(
        max_length=16,
        choices=SCHEDULE_KIND,
        default="monthly",
        db_index=True
    )

    # نوع المهمة + التصنيف
    task_type = models.ForeignKey(
        "performance.TaskType",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="recurring_definitions"
    )

    task_category = models.ForeignKey(
        "performance.TaskCategory",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="recurring_definitions"
    )

    # سياسات التطبيق
    progress_policy = models.ForeignKey(
        "performance.TaskProgressPolicy",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="recurring_definitions"
    )

    sla_policy = models.ForeignKey(
        "performance.TaskSLAPolicy",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="recurring_definitions"
    )

    # الربط مع الهدف
    objective = models.ForeignKey(
        "performance.Objective",
        on_delete=models.CASCADE,
        related_name="recurring_task_definitions"
    )

    # نطاق القسم / الفريق (اختياري)
    department = models.ForeignKey(
        "hr.Department",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="recurring_definitions_department",
    )

    team = models.ForeignKey(
        "hr.Department",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="recurring_definitions_team",
    )

    # عدد التكرار (مثلاً 864 مكالمة شهرياً)
    target_count = models.PositiveIntegerField(default=0)

    # وصف المهمة التي ستولد
    description = models.TextField(blank=True)

    # استثناء موظفين
    excluded_employees = models.ManyToManyField(
        "hr.Employee",
        blank=True,
        related_name="excluded_from_recurring_tasks"
    )

    class Meta:
        db_table = "perf_task_recurring_definition"
        ordering = ("company", "name")
        indexes = [
            models.Index(fields=["company", "active"]),
            models.Index(fields=["schedule_kind"]),
        ]

    def __str__(self):
        return self.name

# ------------------------------------------------------------
# TaskWatcher
# ------------------------------------------------------------
class TaskWatcher(
    
    CompanyOwnedMixin,
    TimeStampedMixin,
    UserStampedMixin,
    ActivableMixin,
    models.Model
):
    """
    مستخدمون يراقبون المهمة (Watchers) – يتلقون إشعارات أو لديهم صلاحية متابعة.
    """

    company = models.ForeignKey(
        "base.Company",
        on_delete=models.PROTECT,
        related_name="task_watchers"
    )

    task = models.ForeignKey(
        "performance.Task",
        on_delete=models.CASCADE,
        related_name="watcher_links"
    )

    employee = models.ForeignKey(
        "hr.Employee",
        on_delete=models.CASCADE,
        related_name="task_watcher_links"
    )

    class Meta:
        db_table = "perf_task_watcher"
        unique_together = [("task", "employee")]
        indexes = [
            models.Index(fields=["task", "employee"]),
        ]

    def __str__(self):
        return f"{self.employee.name} watching {self.task.title}"

# ------------------------------------------------------------
# TaskDependency
# ------------------------------------------------------------
class TaskDependency(
    CompanyOwnedMixin,
    TimeStampedMixin,
    UserStampedMixin,
    ActivableMixin,
    models.Model
):
    """
    علاقة اعتماد: مهمة لا تبدأ قبل اكتمال مهمة أخرى (depends_on)
    """

    company = models.ForeignKey(
        "base.Company",
        on_delete=models.PROTECT,
        related_name="task_dependencies"
    )

    task = models.ForeignKey(
        "performance.Task",
        on_delete=models.CASCADE,
        related_name="dependencies"
    )

    depends_on = models.ForeignKey(
        "performance.Task",
        on_delete=models.CASCADE,
        related_name="unlocking"
    )

    class Meta:
        db_table = "perf_task_dependency"
        unique_together = [("task", "depends_on")]
        indexes = [
            models.Index(fields=["task", "depends_on"]),
        ]

    def __str__(self):
        return f"{self.task.title} depends on {self.depends_on.title}"


# ------------------------------------------------------------
# Task (الدعم الكامل بعد المرحلة الثانية)
# ------------------------------------------------------------

class Task( TimeStampedMixin, UserStampedMixin, ActivableMixin, models.Model ):
    """
    مهمة تنفيذية داخل Objective، مع دعم SLA، Subtasks،
    السياسات الديناميكية، التقدم، الجودة، الكفاءة، والمراجعين.
    """

    # -----------------------------------------
    # العلاقات الأساسية
    # -----------------------------------------
    company   = models.ForeignKey("base.Company", on_delete=models.PROTECT, related_name="perf_tasks")
    objective = models.ForeignKey("performance.Objective", on_delete=models.CASCADE, related_name="tasks")
    kpi       = models.ForeignKey("performance.KPI", null=True, blank=True, on_delete=models.SET_NULL, related_name="tasks")

    title       = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    # -----------------------------------------
    # حالة ديناميكية
    # -----------------------------------------
    status = models.ForeignKey(
        "performance.TaskStatus",
        on_delete=models.PROTECT,
        related_name="tasks",
        null=True,
        blank=False,
    )

    # -----------------------------------------
    # نوع وتصنيف المهمة (Global)
    # -----------------------------------------
    task_type = models.ForeignKey(
        "performance.TaskType",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="tasks"
    )

    task_category = models.ForeignKey(
        "performance.TaskCategory",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="tasks"
    )

    # -----------------------------------------
    # سياسة SLA وسياسة التقدم
    # -----------------------------------------
    sla_policy = models.ForeignKey(
        "performance.TaskSLAPolicy",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="tasks"
    )

    progress_policy = models.ForeignKey(
        "performance.TaskProgressPolicy",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="tasks"
    )

    # -----------------------------------------
    # الوقت والتقديرات
    # تقديرات الوقت تُخزّن بالدقائق لأنها أفضل وحدة أساسية للحساب:
    # - تسهّل حساب النسبة (actual / estimated)
    # - مناسبة لجمع ومقارنة المهام عبر الأيام والأسابيع
    # - شائعة في أنظمة الأداء و-SLA و-WFM
    # المهام الطويلة لا تتعارض مع هذا التصميم؛ يمكن تحويل الدقائق لاحقاً إلى ساعات/أيام عند العرض.
    # -----------------------------------------
    estimated_minutes = models.PositiveIntegerField(default=0)
    actual_minutes    = models.PositiveIntegerField(default=0)

    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    due_date = models.DateField(null=True, blank=True)

    # -----------------------------------------
    # الجودة ومراجعة الجودة
    # -----------------------------------------
    quality_score_pct = models.PositiveIntegerField(default=0)
    quality_pct       = models.PositiveIntegerField(default=100)

    quality_reviewer = models.ForeignKey(
        "hr.Employee",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_performance_tasks"
    )
    quality_reviewed_at = models.DateTimeField(null=True, blank=True)
    quality_notes = models.TextField(blank=True)

    # -----------------------------------------
    # مؤشرات الأداء الديناميكية
    # -----------------------------------------
    timeliness_pct = models.PositiveIntegerField(default=100)
    efficiency_pct = models.PositiveIntegerField(default=100)

    # -----------------------------------------
    # البلوك (مع تحديد داخلي/خارجي)
    # -----------------------------------------
    blocked_reason = models.TextField(blank=True)
    blocked_external = models.BooleanField(default=False)

    # -----------------------------------------
    # Subtasks / Dependencies
    # -----------------------------------------
    parent_task = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="subtasks"
    )

    depends_on = models.ManyToManyField(
        "self",
        blank=True,
        symmetrical=False,
        related_name="blocking_tasks"
    )

    # -----------------------------------------
    # المالك والمتابعون
    # -----------------------------------------
    owner = models.ForeignKey(
        "hr.Employee",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="owned_tasks"
    )

    assignee = models.ForeignKey(
        "hr.Employee",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="performance_tasks"
    )

    watchers = models.ManyToManyField(
        "hr.Employee",
        blank=True,
        related_name="watched_tasks",
        through = "TaskWatcher"
    )

    # -----------------------------------------
    # نسب الإنجاز
    # -----------------------------------------
    percent_complete = models.PositiveIntegerField(default=0)

    # -----------------------------------------
    # تجميد المهمة
    # -----------------------------------------
    is_locked = models.BooleanField(default=False)
    locked_at = models.DateTimeField(null=True, blank=True)

    # -----------------------------------------
    # مصدر المهمة المؤقتة
    # -----------------------------------------
    temporary_source_type = models.CharField(max_length=32, blank=True)
    temporary_source_ref = models.CharField(max_length=64, blank=True)

    class Meta:
        db_table = "perf_task"
        indexes = [
            models.Index(fields=["company", "objective"]),
            models.Index(fields=["due_date"]),
            models.Index(fields=["status"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(percent_complete__gte=0, percent_complete__lte=100),
                name="chk_task_percent_0_100",
            )
        ]

    def __str__(self):
        return self.title

    # ------------------------------------------------------------
    # VALIDATION
    # ------------------------------------------------------------
    def clean(self):
        super().clean()

        if self.objective and self.company and self.objective.company_id != self.company_id:
            raise ValidationError({"objective": "Objective must belong to same company."})

        if self.kpi and self.kpi.company_id != self.company_id:
            raise ValidationError({"kpi": "KPI must belong to same company."})

        if self.assignee and self.assignee.company_id != self.company_id:
            raise ValidationError({"assignee": "Assignee must belong to same company."})

        if self.quality_reviewer and self.quality_reviewer.company_id != self.company_id:
            raise ValidationError({"quality_reviewer": "Reviewer must belong to same company."})

        if self.is_locked:
            raise ValidationError("Cannot modify locked tasks.")

    # ------------------------------------------------------------
    # SAVE LOGIC
    # ------------------------------------------------------------
    def save(self, *args, **kwargs):

        # --------------------------------------------------------
        # 1) منع التعديل إذا كانت المهمة مجمّدة
        # --------------------------------------------------------
        if self.is_locked:
            raise ValidationError("Cannot modify a locked task.")

        now = timezone.now()

        # --------------------------------------------------------
        # 2) ضبط started_at و completed_at حسب الحالة
        #    (نترك منطقك الحالي كما هو)
        # --------------------------------------------------------
        if self.status:
            if self.status.code == "in_progress" and not self.started_at:
                self.started_at = now

            if self.status.is_closed and not self.completed_at:
                self.completed_at = now

        # --------------------------------------------------------
        # 3) مراجعة الجودة
        # --------------------------------------------------------
        if self.quality_score_pct > 0 and not self.quality_reviewed_at:
            self.quality_reviewed_at = now

        # --------------------------------------------------------
        # 4) تطبيق جميع السياسات (SLA + Efficiency + Progress + Dependencies + Quality)
        # --------------------------------------------------------
        from performance import services  # LAZY IMPORT
        services.TaskPolicyEngine.apply(self)

        # --------------------------------------------------------
        # 5) حفظ المهمة فعلياً
        # --------------------------------------------------------
        super().save(*args, **kwargs)

        # --------------------------------------------------------
        # 6) رفع التجميع إلى الـ Objective
        # --------------------------------------------------------
        if self.objective_id:
            self.objective.recompute_progress_and_score()
            self.objective.save(update_fields=["progress_pct", "score_pct"])


# ------------------------------------------------------------
# KPI
# ------------------------------------------------------------

class KPIType(ActivableMixin, TimeStampedMixin, UserStampedMixin, models.Model):
    """
    نوع KPI (Global): Quality, Productivity, SLA, Financial...
    """
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=64, unique=True, db_index=True)
    description = models.TextField(blank=True)

    class Meta:
        db_table = "perf_kpi_type"
        ordering = ("name",)
        indexes = [
            models.Index(fields=["active"]),
            models.Index(fields=["code"]),
        ]

    def __str__(self):
        return self.name

class KPICategory(ActivableMixin, TimeStampedMixin, UserStampedMixin, models.Model):
    """
    تصنيف KPI (Global): Strategic, Operational, Technical...
    """
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=64, unique=True, db_index=True)
    description = models.TextField(blank=True)

    class Meta:
        db_table = "perf_kpi_category"
        ordering = ("name",)
        indexes = [
            models.Index(fields=["active"]),
            models.Index(fields=["code"]),
        ]

    def __str__(self):
        return self.name

class KPICalculationMethod(ActivableMixin, TimeStampedMixin, UserStampedMixin, models.Model):
    """
    طريقة حساب KPI: Dynamic formula definition stored in DB.
    """

    code = models.CharField(max_length=64, unique=True, db_index=True)
    name = models.CharField(max_length=255)

    FORMULA_CHOICES = [
        ("ratio", "current / target"),
        ("inverse_ratio", "target / current"),
        ("progressive", "progressive scaling upto 200%"),
        ("manual", "Manual score (entered directly)"),
    ]

    formula_type = models.CharField(max_length=32, choices=FORMULA_CHOICES, default="ratio")

    green_threshold_pct = models.PositiveIntegerField(default=90)
    yellow_threshold_pct = models.PositiveIntegerField(default=70)

    description = models.TextField(blank=True)

    class Meta:
        db_table = "perf_kpi_calc_method"
        ordering = ("name",)

    def __str__(self):
        return self.name


class KPI( TimeStampedMixin, UserStampedMixin, ActivableMixin):
    """
    مؤشر أداء رئيسي داخل Objective، مع تخزين نتائج attainment/score.
    """
    UNIT_CHOICES = [
        ("#", "Count"),
        ("%", "Percent"),
        ("IQD", "IQD"),
        ("USD", "USD"),
        ("hrs", "Hours"),
        ("min", "Minutes"),  # ← أضفت هذه
        ("custom", "Custom"),
    ]

    company   = models.ForeignKey("base.Company", on_delete=models.PROTECT, related_name="kpis")
    objective = models.ForeignKey("performance.Objective", on_delete=models.CASCADE, related_name="kpis")

    name        = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    kpi_type = models.ForeignKey(
        "performance.KPIType",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="kpis"
    )

    category = models.ForeignKey(
        "performance.KPICategory",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="kpis"
    )


    unit             = models.CharField(max_length=10, choices=UNIT_CHOICES, default="#")
    higher_is_better = models.BooleanField(default=True, help_text="If False, lower values score higher")

    target_value   = models.DecimalField(max_digits=16, decimal_places=4)
    baseline_value = models.DecimalField(max_digits=16, decimal_places=4, null=True, blank=True)
    current_value  = models.DecimalField(max_digits=16, decimal_places=4, null=True, blank=True)

    calculation_method = models.ForeignKey(
        "performance.KPICalculationMethod",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="kpis",
        help_text="Dynamic calculation rule for KPI."
    )


    # وزن داخل الـ Objective
    weight_pct = models.PositiveIntegerField(default=100)

    owner = models.ForeignKey(
        "hr.Employee",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="owned_kpis",
        help_text="Employee responsible for updating KPI data."
    )

    data_source = models.CharField(
        max_length=16,
        choices=[("manual", "Manual"), ("external", "External System")],
        default="manual"
    )

    external_source_ref = models.CharField(
        max_length=128,
        blank=True,
        help_text="Reference if KPI data comes from external system."
    )

    is_locked = models.BooleanField(default=False)
    locked_at = models.DateTimeField(null=True, blank=True)


    # Stored computes
    attainment_pct = models.PositiveIntegerField(default=0, help_text="0..100% of target achieved", db_index=True)
    score_pct      = models.PositiveIntegerField(default=0, help_text="0..100 normalized score")


    class Meta:
        db_table = "perf_kpi"
        indexes = [
            models.Index(fields=["company", "objective"]),
            models.Index(fields=["attainment_pct", "score_pct"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(weight_pct__gte=0, weight_pct__lte=100),
                name="chk_kpi_weight_0_100",
            ),
            models.CheckConstraint(
                check=models.Q(attainment_pct__gte=0, attainment_pct__lte=200),
                name="chk_kpi_att_0_200",
            ),
            models.CheckConstraint(
                check=models.Q(score_pct__gte=0, score_pct__lte=100),
                name="chk_kpi_score_0_100",
            ),
        ]
        permissions = [
            ("recompute_kpi", "Can recompute KPI"),
            ("set_kpi_manual_value", "Can set manual KPI value"),
        ]

    def __str__(self):
        return f"{self.objective.title}: {self.name}"

    def clean(self):
        super().clean()
        if self.objective and self.company and self.objective.company_id != self.company_id:
            raise ValidationError({"objective": "Objective must belong to the same company."})

    def recompute(self):
        """
        حساب KPI يعتمد الآن على طريقة الحساب المخزنة في DB.
        """

        # Locked KPIs cannot be updated
        if self.is_locked:
            return

        # Manual calculation: score entered externally / admin
        if self.calculation_method and self.calculation_method.formula_type == "manual":
            return  # no automatic changes

        if self.current_value is None or self.target_value in (None, 0):
            self.attainment_pct = 0
            self.score_pct = 0
            return

        cur = float(self.current_value)
        tgt = float(self.target_value)

        method = self.calculation_method.formula_type if self.calculation_method else "ratio"

        if method == "ratio":
            att = (cur / tgt) * 100.0

        elif method == "inverse_ratio":
            att = (tgt / cur) * 100.0 if cur > 0 else 100.0

        elif method == "progressive":
            # cap to 200%
            att = min((cur / tgt) * 100.0, 200.0)

        else:  # fallback
            att = (cur / tgt) * 100.0

        self.attainment_pct = int(round(min(att, 200)))
        self.score_pct = int(round(max(0, min(100, att))))


    def save(self, *args, **kwargs):

        if self.is_locked:
            return  # locked KPIs cannot be modified

        super().save(*args, **kwargs)

        self.recompute()

        super().save(update_fields=["attainment_pct", "score_pct"])

        self.objective.recompute_progress_and_score()
        self.objective.save(update_fields=["progress_pct", "score_pct"])



# ------------------------------------------------------------------
# Objective , ObjectiveStatus , ObjectiveType and ObjectiveCategory
# ------------------------------------------------------------------

class ObjectiveStatus(ActivableMixin, TimeStampedMixin, UserStampedMixin, models.Model):
    """
    حالة الهدف: ديناميكية، Global (غير مرتبطة بشركة معيّنة).
    مثل: Draft, Active, Paused, Done, Cancelled, Archived...
    """

    name = models.CharField(max_length=255)
    code = models.CharField(max_length=64, unique=True, db_index=True)
    sequence = models.PositiveIntegerField(default=10, help_text="Sorting order")
    description = models.TextField(blank=True)

    class Meta:
        db_table = "perf_objective_status"
        ordering = ("sequence", "name")
        indexes = [
            models.Index(fields=["active"]),
            models.Index(fields=["code"]),
        ]

    def __str__(self):
        return self.name

class ObjectiveType(ActivableMixin, TimeStampedMixin, UserStampedMixin, models.Model):
    """
    نوع الهدف (Global): جودة، إنتاجية، تشغيلي، تطوير، سلوكي...
    يمكن استخدامه لتجميع الأهداف حسب النوع
    وربطه بسياسة احتساب افتراضية تختلف من نوع لآخر.
    """

    name = models.CharField(max_length=255)
    code = models.CharField(max_length=64, blank=True, db_index=True)
    description = models.TextField(blank=True)

    # سياسة احتساب افتراضية لهذا النوع (اختياري)
    default_scoring_policy = models.ForeignKey(
        "performance.EmployeeObjectiveScoringPolicy",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="objective_type_defaults",
        help_text="Optional default scoring policy for all Objectives of this type.",
    )

    class Meta:
        db_table = "perf_objective_type"
        indexes = [
            models.Index(fields=["active"]),
            models.Index(fields=["code"]),
        ]
        ordering = ("name",)

    def __str__(self):
        return self.name

class ObjectiveCategory(ActivableMixin, TimeStampedMixin, UserStampedMixin, models.Model):
    """
    تصنيف الهدف (Global): استراتيجي، تشغيلي، تطوير، جودة، مبادرة...
    يُستخدم للتحليل والتقارير وتصفية الأهداف.
    """

    name = models.CharField(max_length=255)
    code = models.CharField(max_length=64, blank=True, db_index=True)
    description = models.TextField(blank=True)

    class Meta:
        db_table = "perf_objective_category"
        indexes = [
            models.Index(fields=["active"]),
            models.Index(fields=["code"]),
        ]
        ordering = ("name",)

    def __str__(self):
        return self.name

class Objective(  CompanyOwnedMixin, TimeStampedMixin, UserStampedMixin, ActivableMixin, models.Model):
    """
    الهدف: وعاء KPIs/Tasks + تجميع progress/score + مشاركين + Rollup.
    """
    # -------------------
    # العلاقات الأساسية
    # -------------------
    company = models.ForeignKey(
        "base.Company",
        on_delete=models.PROTECT,
        related_name="objectives",
    )

    reviewer = models.ForeignKey(
        "hr.Employee",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_objectives",
    )

    code        = models.CharField(max_length=32, blank=True)
    title       = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    # -------------------
    # نوع الهدف + تصنيفه
    # -------------------
    objective_type = models.ForeignKey(
        "performance.ObjectiveType",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="objectives",
        help_text="Type of this objective (Quality, Productivity, Operations, etc.)",
    )

    category = models.ForeignKey(
        "performance.ObjectiveCategory",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="objectives",
        help_text="Category (Strategic, Operational, Development, etc.)",
    )

    # -------------------
    # Hierarchy (Company → Division → Department → Section → Team → Employee)
    # -------------------
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="children",
        help_text="Parent objective in the hierarchy.",
    )

    hierarchy_level = models.PositiveIntegerField(
        default=1,
        help_text="1 = Company, 2 = Division, 3 = Department, 4 = Section, 5 = Team, 6 = Employee",
    )

    ROLLUP_CHOICES = [
        ("average", "Average of children"),
        ("weighted", "Weighted by child weight_pct"),
        ("none", "Compute from own KPIs/Tasks only"),
    ]

    rollup_strategy = models.CharField(
        max_length=16,
        choices=ROLLUP_CHOICES,
        default="none",
    )

    # -------------------
    # المدة الزمنية
    # -------------------
    date_start = models.DateField()
    date_end   = models.DateField(null=True, blank=True)

    status = models.ForeignKey(
        "performance.ObjectiveStatus",
        on_delete=models.PROTECT,
        related_name="objectives",
        null=True,
        blank=False,
        help_text="Dynamic status of the objective",
    )

    # -------------------
    # Target Scope
    # -------------------
    TARGET = [
        ("company",   "Company"),
        ("department","Department"),
        ("employee",  "Employee"),
    ]

    target_kind = models.CharField(
        max_length=12,
        choices=TARGET,
        default="company",
        db_index=True,
    )

    target_department = models.ForeignKey(
        "hr.Department",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="target_objectives",
    )

    target_employee = models.ForeignKey(
        "hr.Employee",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="target_objectives",
    )

    # وزن الهدف داخل التقييم النهائي
    weight_pct = models.PositiveIntegerField(
        default=100,
        help_text="0..100 (%) weight",
    )

    # -------------------
    # Scoring Policy Override
    # -------------------
    scoring_policy = models.ForeignKey(
        "performance.EmployeeObjectiveScoringPolicy",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="objectives",
        help_text="Override scoring policy for this objective. If empty, use ObjectiveType or Company default.",
    )

    # -------------------
    # التجميعات المخزنة
    # -------------------
    progress_pct = models.PositiveIntegerField(
        default=0,
        help_text="Aggregated Tasks progress (0..100)",
        db_index=True,
    )

    score_pct = models.PositiveIntegerField(
        default=0,
        help_text="Aggregated KPI score (0..100)",
    )



    class Meta:
        db_table = "perf_objective"
        indexes = [
            models.Index(fields=["company", "status"]),
            models.Index(fields=["company", "objective_type"]),
            models.Index(fields=["company", "category"]),
            models.Index(fields=["date_start", "date_end"]),
            models.Index(fields=["parent"]),
            models.Index(fields=["hierarchy_level"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(weight_pct__gte=0, weight_pct__lte=100),
                name="chk_objective_weight_0_100",
            ),
            models.CheckConstraint(
                check=(models.Q(progress_pct__gte=0, progress_pct__lte=100)),
                name="chk_objective_progress_0_100",
            ),
            models.CheckConstraint(
                check=(models.Q(score_pct__gte=0, score_pct__lte=100)),
                name="chk_objective_score_0_100",
            ),
            models.CheckConstraint(
                check=(
                    models.Q(date_end__isnull=True) |
                    models.Q(date_start__lte=models.F("date_end"))
                ),
                name="chk_objective_dates",
            ),
        ]
        permissions = [
            ("close_objective", "Can close/archive objective"),
            ("manage_objective_participants", "Can manage objective participants"),
            ("manage_objective_kpis", "Can manage objective KPIs"),
            ("manage_objective_tasks", "Can manage objective tasks"),
        ]

    def __str__(self):
        return self.title

    # ------------------------------------------------------------
    # Validation Logic
    # ------------------------------------------------------------
    def clean(self):
        super().clean()

        # reviewer must belong to the same company
        if self.reviewer and self.reviewer.company_id != self.company_id:
            raise ValidationError({"reviewer": "Reviewer must belong to the same company."})

        # parent must belong to same company
        if self.parent and self.parent.company_id != self.company_id:
            raise ValidationError({"parent": "Parent objective must belong to the same company."})

        # prevent loops
        if self.parent_id and self.parent_id == self.id:
            raise ValidationError({"parent": "Objective cannot be parent of itself."})

        # auto-set hierarchy based on parent
        if self.parent:
            self.hierarchy_level = (self.parent.hierarchy_level or 1) + 1

        # target validations
        if self.target_kind == "company":
            if self.target_department or self.target_employee:
                raise ValidationError("Company-wide objectives cannot have department or employee targets.")

        elif self.target_kind == "department":
            if not self.target_department:
                raise ValidationError({"target_department": "Department must be selected."})
            if self.target_employee:
                raise ValidationError({"target_employee": "Cannot select employee for department-level objective."})

        elif self.target_kind == "employee":
            if not self.target_employee:
                raise ValidationError({"target_employee": "Employee must be selected."})
            if self.target_department:
                raise ValidationError({"target_department": "Cannot select department for employee-level objective."})

        if self.scoring_policy and self.scoring_policy.company_id != self.company_id:
            raise ValidationError({"scoring_policy": "Scoring policy must belong to the same company."})


    # ------------------------------------------------------------
    # Recompute progress and score
    # ------------------------------------------------------------
    def recompute_progress_and_score(self):
        """
        Aggregation logic:
        1) If rollup and children exist → aggregate from children.
        2) Otherwise → aggregate from own KPIs and Tasks.
        """
        # Children rollup
        children = list(self.children.filter(active=True).all())

        if children and self.rollup_strategy != "none":

            if self.rollup_strategy == "average":
                self.progress_pct = int(round(sum(c.progress_pct for c in children) / len(children)))
                self.score_pct = int(round(sum(c.score_pct for c in children) / len(children)))

            elif self.rollup_strategy == "weighted":
                total_w = sum(c.weight_pct for c in children) or 1
                self.progress_pct = int(round(sum(c.progress_pct * c.weight_pct for c in children) / total_w))
                self.score_pct = int(round(sum(c.score_pct * c.weight_pct for c in children) / total_w))

            return

        # Original aggregation from own KPIs/Tasks
        tasks = Task.objects.filter(objective=self).exclude(status="cancelled")

        if tasks.exists():
            self.progress_pct = int(round(sum(t.percent_complete for t in tasks) / tasks.count()))
        else:
            self.progress_pct = 0

        kpis = KPI.objects.filter(objective=self)

        if kpis.exists():
            total_w = sum(k.weight_pct or 0 for k in kpis) or (kpis.count() * 100)
            num = sum((k.score_pct or 0) * (k.weight_pct or 100) for k in kpis)
            self.score_pct = max(0, min(100, int(round(num / total_w))))
        else:
            self.score_pct = 0

    # ------------------------------------------------------------
    # Participants Collection
    # ------------------------------------------------------------
    def _collect_department_ids(self):
        from hr.models import Department

        dept_ids = set()

        # target = department
        if self.target_kind == "department" and self.target_department_id:
            dept_ids.add(self.target_department_id)

            parent_path = self.target_department.parent_path or ""
            if parent_path:
                q = Department.objects.filter(
                    company_id=self.company_id,
                    parent_path__startswith=parent_path,
                ).values_list("id", flat=True)
                dept_ids.update(q)

        # explicit department assignments
        for a in self.dept_assignments.select_related("department").all():
            if not a.department_id:
                continue
            dept_ids.add(a.department_id)

            if a.include_children:
                parent_path = a.department.parent_path or ""
                if parent_path:
                    q = Department.objects.filter(
                        company_id=self.company_id,
                        parent_path__startswith=parent_path,
                    ).values_list("id", flat=True)
                    dept_ids.update(q)

        return dept_ids

    def _collect_employee_ids(self):
        from hr.models import Employee

        emp_ids = set()

        # direct target employee
        if self.target_kind == "employee" and self.target_employee_id:
            emp_ids.add(self.target_employee_id)

        # explicit employee assignments
        emp_ids.update(self.employee_assignments.values_list("employee_id", flat=True))

        # employees from departments
        dept_ids = self._collect_department_ids()
        if dept_ids:
            q = Employee.objects.filter(
                company_id=self.company_id,
                active=True,
                department_id__in=list(dept_ids),
            ).values_list("id", flat=True)
            emp_ids.update(q)

        return emp_ids

    @transaction.atomic
    def _rebuild_participants(self):
        target_ids  = set(self._collect_employee_ids())
        current_ids = set(self.participants.values_list("employee_id", flat=True))

        to_add = target_ids - current_ids
        to_del = current_ids - target_ids

        if to_del:
            ObjectiveParticipant.objects.filter(objective=self, employee_id__in=list(to_del)).delete()

        if to_add:
            ObjectiveParticipant.objects.bulk_create(
                [ObjectiveParticipant(objective=self, employee_id=eid) for eid in to_add],
                ignore_conflicts=True,
            )

    # ------------------------------------------------------------
    # Compute Employee Scores (Final – Using ObjectiveScoreEngine)
    # ------------------------------------------------------------
    def compute_employee_scores(self):
        """
        Computes EmployeeObjectiveScore for each participant with:
        - Dynamic scoring policies (Objective → Type → Company)
        - KPI scores
        - Task progress
        - Timeliness / Efficiency / Quality (from TaskPolicyEngine)
        - Contribution %
        """

        from performance.models import (
            EmployeeObjectiveScore,
            EmployeeObjectiveScoringPolicy,
            Task,
            KPI,
        )
        from performance.services import ObjectiveScoreEngine

        participants = self.participants.select_related("employee").all()
        if not participants:
            return

        # ------------------------------------------------------------
        # 1) جمع كل المهام و KPIs
        # ------------------------------------------------------------
        all_tasks = Task.objects.filter(objective=self, active=True)
        all_kpis = KPI.objects.filter(objective=self, active=True)

        # ------------------------------------------------------------
        # 2) تحديد سياسة الاحتساب (ثلاث مستويات)
        # ------------------------------------------------------------
        policy = None

        # مستوى 1: السياسة المخصصة للهدف نفسه
        if self.scoring_policy and self.scoring_policy.active:
            policy = self.scoring_policy

        # مستوى 2: سياسة النوع (ObjectiveType)
        if (
            policy is None
            and self.objective_type
            and self.objective_type.default_scoring_policy
            and self.objective_type.default_scoring_policy.active
            and self.objective_type.default_scoring_policy.company_id == self.company_id
        ):
            policy = self.objective_type.default_scoring_policy

        # مستوى 3: سياسة الشركة الافتراضية
        if policy is None:
            policy = EmployeeObjectiveScoringPolicy.objects.filter(
                company=self.company,
                active=True,
            ).order_by("-id").first()

        # fallback weights (ضمان عدم حصول قسمة صفر)
        if policy:
            w_tasks = policy.tasks_weight_pct or 0
            w_kpi = policy.kpi_weight_pct or 0
            w_time = policy.timeliness_weight_pct or 0
            w_eff = policy.efficiency_weight_pct or 0
            w_qual = policy.quality_weight_pct or 0
        else:
            w_tasks, w_kpi, w_time, w_eff, w_qual = 30, 30, 15, 10, 15

        total_w = w_tasks + w_kpi + w_time + w_eff + w_qual
        if total_w <= 0:
            total_w = 100
            w_tasks, w_kpi, w_time, w_eff, w_qual = 30, 30, 15, 10, 15

        # normalize
        w_tasks_n = w_tasks / total_w
        w_kpi_n = w_kpi / total_w
        w_time_n = w_time / total_w
        w_eff_n = w_eff / total_w
        w_qual_n = w_qual / total_w

        # ------------------------------------------------------------
        # 3) حساب النتائج لكل موظف
        # ------------------------------------------------------------
        for p in participants:
            emp = p.employee

            # ------------------------------
            # progress من المهام
            # ------------------------------
            emp_tasks = all_tasks.filter(
                models.Q(assignee=emp) |
                models.Q(assignee__isnull=True)
            )

            if emp_tasks.exists():
                tasks_progress = int(round(sum(t.percent_complete for t in emp_tasks) / emp_tasks.count()))
            else:
                tasks_progress = 0

            # ------------------------------
            # KPI scoring
            # ------------------------------
            emp_kpis = [k.score_pct for k in all_kpis]
            kpi_score = int(round(sum(emp_kpis) / len(emp_kpis))) if emp_kpis else 0

            # ------------------------------
            # contribution %
            # ------------------------------
            if all_tasks.count() > 0:
                contribution_pct = int(round((emp_tasks.count() / all_tasks.count()) * 100))
            else:
                contribution_pct = 0

            # ------------------------------
            # Timeliness / Efficiency / Quality
            # ------------------------------
            agg = ObjectiveScoreEngine.aggregate_for_employee(self, emp)

            timeliness_pct = agg["timeliness"]
            efficiency_pct = agg["efficiency"]
            quality_pct = agg["quality"]

            # ------------------------------
            # Final Score (weighted formula)
            # ------------------------------
            final = int(
                round(
                    (tasks_progress * w_tasks_n) +
                    (kpi_score * w_kpi_n) +
                    (timeliness_pct * w_time_n) +
                    (efficiency_pct * w_eff_n) +
                    (quality_pct * w_qual_n)
                )
            )

            # ------------------------------
            # Save results
            # ------------------------------
            EmployeeObjectiveScore.objects.update_or_create(
                objective=self,
                employee=emp,
                defaults={
                    "tasks_progress_pct": tasks_progress,
                    "kpi_score_pct": kpi_score,
                    "contribution_pct": contribution_pct,
                    "timeliness_pct": timeliness_pct,
                    "efficiency_pct": efficiency_pct,
                    "quality_pct": quality_pct,
                    "final_score_pct": final,
                }
            )

    # ------------------------------------------------------------
    # Save Hook
    # ------------------------------------------------------------
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.recompute_progress_and_score()
        super().save(update_fields=["progress_pct", "score_pct"])
        self._rebuild_participants()
        self.compute_employee_scores()


# Objective Assignments & Participants
# ------------------------------------------------------------
class ObjectiveDepartmentAssignment(TimeStampedMixin, UserStampedMixin):
    """إسناد هدف إلى قسم معيّن (مع خيار تضمين الأبناء)."""
    objective       = models.ForeignKey("performance.Objective", on_delete=models.CASCADE, related_name="dept_assignments")
    department      = models.ForeignKey("hr.Department", on_delete=models.CASCADE, related_name="objective_assignments")
    include_children = models.BooleanField(default=True)

    def clean(self):
        super().clean()
        # department.company == objective.company
        if (
            self.department_id
            and self.objective_id
            and getattr(self.department, "company_id", None) is not None
            and getattr(self.objective, "company_id", None) is not None
            and self.department.company_id != self.objective.company_id
        ):
            raise ValidationError({"department": "Department must belong to the same company as the Objective."})

    class Meta:
        db_table = "perf_objective_dept_assignment"
        constraints = [
            models.UniqueConstraint(
                fields=["objective", "department"],
                name="perf_obj_dept_uniq",
            ),
        ]
        indexes = [models.Index(fields=["objective", "department"])]
        permissions = [("manage_department_assignments", "Can manage department assignments")]

    def __str__(self):
        return f"{self.objective.title} → {self.department.complete_name} ({'with' if self.include_children else 'no'} children)"


class ObjectiveEmployeeAssignment(TimeStampedMixin, UserStampedMixin):
    """إسناد هدف إلى موظفين محدّدين (إضافة على استهداف الأقسام)."""
    objective = models.ForeignKey("performance.Objective", on_delete=models.CASCADE, related_name="employee_assignments")
    employee  = models.ForeignKey("hr.Employee", on_delete=models.CASCADE, related_name="objective_assignments")

    def clean(self):
        super().clean()
        # employee.company == objective.company
        if (
            self.employee_id
            and self.objective_id
            and getattr(self.employee, "company_id", None) is not None
            and getattr(self.objective, "company_id", None) is not None
            and self.employee.company_id != self.objective.company_id
        ):
            raise ValidationError({"employee": "Employee must belong to the same company as the Objective."})

    class Meta:
        db_table = "perf_objective_employee_assignment"
        constraints = [
            models.UniqueConstraint(
                fields=["objective", "employee"],
                name="perf_obj_emp_uniq",
            ),
        ]
        indexes = [models.Index(fields=["objective", "employee"])]
        permissions = [("manage_employee_assignments", "Can manage employee assignments")]

    def __str__(self):
        return f"{self.objective.title} → {self.employee.name}"


class ObjectiveParticipant(TimeStampedMixin):
    """
    تمثيل مادي (Materialized) للمشاركين في الهدف.
    يُعاد بناؤه عند تغيّر الهدف أو تعييناته.
    """
    objective = models.ForeignKey("performance.Objective", on_delete=models.CASCADE, related_name="participants")
    employee  = models.ForeignKey("hr.Employee", on_delete=models.CASCADE, related_name="objective_participations")

    def clean(self):
        super().clean()
        # employee.company == objective.company
        if (
            self.employee_id
            and self.objective_id
            and getattr(self.employee, "company_id", None) is not None
            and getattr(self.objective, "company_id", None) is not None
            and self.employee.company_id != self.objective.company_id
        ):
            raise ValidationError({"employee": "Participant must belong to the same company as the Objective."})

    class Meta:
        db_table = "perf_objective_participant"
        constraints = [
            models.UniqueConstraint(
                fields=["objective", "employee"],
                name="perf_obj_participant_uniq",
            ),
        ]
        indexes = [models.Index(fields=["employee", "objective"])]
        permissions = [("view_objective_participants", "Can view objective participants")]

    def __str__(self):
        return f"{self.employee.name} ⇢ {self.objective.title}"


class EmployeeObjectiveScoringPolicy(CompanyOwnedMixin, ActivableMixin, TimeStampedMixin, UserStampedMixin, models.Model):
    """
    سياسة احتساب الدرجة النهائية داخل الهدف لكل موظف.
    يتم التحكم بالأوزان من الـ Admin بدون تعديل الكود.

    الأوزان هنا هي نسب مئوية (0..100) وسيتم تطبيعها (normalize) بحيث
    لو لم يكن المجموع 100 بالضبط، نستخدم المجموع الفعلي.
    """

    name = models.CharField(max_length=255)
    code = models.CharField(max_length=64, blank=True)

    # أوزان المؤشرات الفرعية (0..100 لكلٍ منها)
    tasks_weight_pct = models.PositiveIntegerField(
        default=30,
        help_text="Weight for Tasks Progress (0..100)."
    )
    kpi_weight_pct = models.PositiveIntegerField(
        default=30,
        help_text="Weight for KPI Score (0..100)."
    )
    timeliness_weight_pct = models.PositiveIntegerField(
        default=15,
        help_text="Weight for Timeliness (0..100)."
    )
    efficiency_weight_pct = models.PositiveIntegerField(
        default=10,
        help_text="Weight for Time Efficiency (0..100)."
    )
    quality_weight_pct = models.PositiveIntegerField(
        default=15,
        help_text="Weight for Tasks Quality (0..100)."
    )

    class Meta:
        db_table = "perf_employee_objective_scoring_policy"
        indexes = [
            models.Index(fields=["company", "active"]),
        ]
        ordering = ("company", "name")

    def __str__(self):
        return f"{self.company} / {self.name}"

    def clean(self):
        """
        التحقق من أن الأوزان منطقية (0..100) والمجموع > 0.
        لا نفرض أن المجموع = 100 بالضبط لأننا سنقوم بالتطبيع في الحساب.
        """
        super().clean()
        fields = [
            ("tasks_weight_pct", self.tasks_weight_pct),
            ("kpi_weight_pct", self.kpi_weight_pct),
            ("timeliness_weight_pct", self.timeliness_weight_pct),
            ("efficiency_weight_pct", self.efficiency_weight_pct),
            ("quality_weight_pct", self.quality_weight_pct),
        ]

        errors = {}
        for fname, value in fields:
            if value < 0 or value > 100:
                errors[fname] = "Weight must be between 0 and 100."
        if errors:
            raise ValidationError(errors)

        total = sum(v or 0 for _, v in fields)
        if total <= 0:
            raise ValidationError("Total of all weights must be > 0.")


class EmployeeObjectiveScore(TimeStampedMixin, UserStampedMixin):
    """
    Stores the score of each employee inside each Objective.
    This is the MOST important entity for fair evaluation.
    """

    objective = models.ForeignKey(
        "performance.Objective",
        on_delete=models.CASCADE,
        related_name="employee_scores"
    )

    employee = models.ForeignKey(
        "hr.Employee",
        on_delete=models.CASCADE,
        related_name="objective_scores"
    )

    # نسبة مساهمة الموظف داخل الهدف (0..100)
    contribution_pct = models.PositiveIntegerField(default=0)

    # تقدم المهام الخاصة به (0..100)
    tasks_progress_pct = models.PositiveIntegerField(default=0)

    # تقدم KPIs الخاصة به (0..100)
    kpi_score_pct = models.PositiveIntegerField(default=0)

    # الدرجة النهائية داخل الهدف
    final_score_pct = models.PositiveIntegerField(default=0)

    # التزام الموظف بالمواعيد داخل هذا الهدف (0..100)
    timeliness_pct = models.PositiveIntegerField(
        default=100,
        help_text="On-time completion ratio for this objective (0..100)."
    )

    # كفاءة استغلال الوقت (estimated vs actual) داخل هذا الهدف (0..100)
    efficiency_pct = models.PositiveIntegerField(
        default=100,
        help_text="Time efficiency score based on estimated vs actual minutes (0..100)."
    )

    # متوسط جودة تنفيذ المهام المرتبطة بهذا الهدف (0..100)
    quality_pct = models.PositiveIntegerField(
        default=100,
        help_text="Average quality score of tasks within this objective (0..100)."
    )


    class Meta:
        db_table = "perf_employee_objective_score"
        unique_together = [("objective", "employee")]
        indexes = [
            models.Index(fields=["objective", "employee"]),
            models.Index(fields=["final_score_pct"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(contribution_pct__gte=0, contribution_pct__lte=100),
                name="chk_eos_contribution_0_100",
            ),
            models.CheckConstraint(
                check=models.Q(tasks_progress_pct__gte=0, tasks_progress_pct__lte=100),
                name="chk_eos_tasks_progress_0_100",
            ),
            models.CheckConstraint(
                check=models.Q(kpi_score_pct__gte=0, kpi_score_pct__lte=100),
                name="chk_eos_kpi_score_0_100",
            ),
            models.CheckConstraint(
                check=models.Q(final_score_pct__gte=0, final_score_pct__lte=100),
                name="chk_eos_final_score_0_100",
            ),
            models.CheckConstraint(
                check=models.Q(timeliness_pct__gte=0, timeliness_pct__lte=100),
                name="chk_eos_timeliness_0_100",
            ),
            models.CheckConstraint(
                check=models.Q(efficiency_pct__gte=0, efficiency_pct__lte=100),
                name="chk_eos_efficiency_0_100",
            ),
            models.CheckConstraint(
                check=models.Q(quality_pct__gte=0, quality_pct__lte=100),
                name="chk_eos_quality_0_100",
            ),
        ]


    def __str__(self):
        return f"{self.employee.name} → {self.objective.title}: {self.final_score_pct}%"




# ------------------------------------------------------------
# EvaluationType ,and EvaluationApprovalStep
# ------------------------------------------------------------
class EvaluationType(CompanyOwnedMixin, ActivableMixin, TimeStampedMixin, UserStampedMixin, models.Model):
    """
    نوع تقييم (شهري، ربع سنوي، سنوي، أو Ad-hoc) قابل للإدارة من الـ Admin.
    - لا يحتوي منطق الموافقات، فقط تعريف النوع نفسه.
    - سير الموافقات (workflow) سيتم ربطه لاحقاً عبر EvaluationApprovalStep.
    """

    name = models.CharField(max_length=128)
    code = models.CharField(max_length=64, blank=True)
    sequence = models.PositiveSmallIntegerField(default=10, db_index=True)

    # حقل حر يمكن تعديله من الـ Admin بدون أي choices ثابتة في الكود
    frequency_label = models.CharField(
        max_length=64,
        blank=True,
        help_text="وصف حر للتكرار (مثلاً: Monthly / Quarterly / Project-based).",
    )

    description = models.TextField(blank=True)

    class Meta:
        db_table = "perf_evaluation_type"
        ordering = ("company", "sequence", "name")
        indexes = [
            models.Index(
                fields=["company", "active"],
                name="evaltype_comp_active",
            ),
            models.Index(
                fields=["company", "sequence"],
                name="evaltype_comp_seq",
            ),
        ]
        constraints = [
            # كود مميز داخل الشركة الواحدة عند تحديده
            models.UniqueConstraint(
                fields=["company", "code"],
                name="perf_evaltype_company_code_uniq",
                condition=models.Q(code__gt=""),
            ),
        ]

    def __str__(self) -> str:
        return self.name


class EvaluationApprovalStep(CompanyOwnedMixin, ActivableMixin, TimeStampedMixin, UserStampedMixin):
    """
    خطوة موافقة واحدة مرتبطة بنوع تقييم معيّن (EvaluationType).
    يمكن ترتيب خطوات متعددة لكل نوع عبر حقل sequence.

    approver_kind يحدد من هو صاحب الصلاحية في هذه الخطوة:
      - direct_manager      : المدير المباشر للموظف
      - department_manager  : مدير قسم الموظف
      - manager_chain       : مدير على مستوى أعلى (manager_level = 1,2,3...)
      - employee            : موظف محدد بالاسم (approver_employee)
      - group               : مجموعة/Role من الـ Auth Group (approver_group)

    المنطق الفعلي لاستخدام هذه الحقول سيتم إضافته لاحقًا داخل Evaluation workflow.
    """

    class ApproverKind(models.TextChoices):
        DIRECT_MANAGER     = "direct_manager", "Direct Manager"
        DEPARTMENT_MANAGER = "department_manager", "Department Manager"
        MANAGER_CHAIN      = "manager_chain", "Manager Chain (Level)"
        EMPLOYEE           = "employee", "Specific Employee"
        GROUP              = "group", "Specific Group/Role"

    evaluation_type = models.ForeignKey(
        "performance.EvaluationType",
        on_delete=models.CASCADE,
        related_name="approval_steps",
    )

    name = models.CharField(max_length=128)
    code = models.CharField(max_length=64, blank=True)

    sequence = models.PositiveSmallIntegerField(
        default=10,
        db_index=True,
        help_text="ترتيب الخطوة داخل سير الموافقات (كلما قل الرقم كانت الخطوة أبكر).",
    )

    approver_kind = models.CharField(
        max_length=32,
        choices=ApproverKind.choices,
        default=ApproverKind.DIRECT_MANAGER,
    )

    # يستخدم مع manager_chain لتحديد مستوى المدير (1 = المدير المباشر، 2 = مدير المدير، ...إلخ)
    manager_level = models.PositiveSmallIntegerField(
        default=1,
        help_text="يُستخدم فقط عند اختيار MANAGER_CHAIN لتحديد مستوى المدير في السلسلة.",
    )

    # عندما يكون approver_kind = EMPLOYEE
    approver_employee = models.ForeignKey(
        "hr.Employee",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approval_steps_as_specific_approver",
    )

    # عندما يكون approver_kind = GROUP
    approver_group = models.ForeignKey(
        "auth.Group",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="evaluation_approval_steps",
    )

    description = models.TextField(blank=True)

    class Meta:
        db_table = "perf_evaluation_approval_step"
        ordering = ("company", "evaluation_type", "sequence", "id")
        indexes = [
            models.Index(
                fields=["company", "evaluation_type", "sequence"],
                name="evalstep_comp_type_seq",
            ),
        ]
        constraints = [
            # كود مميز داخل الشركة ونوع التقييم عند تحديده
            models.UniqueConstraint(
                fields=["company", "evaluation_type", "code"],
                name="perf_evalstep_company_type_code_uniq",
                condition=models.Q(code__gt=""),
            ),
            # manager_level لا يقل عن 1
            models.CheckConstraint(
                check=models.Q(manager_level__gte=1),
                name="chk_evalstep_manager_level_gte_1",
            ),
        ]

    def clean(self):
        super().clean()

        # تحقق من الحقول المطلوبة حسب نوع الـ approver_kind
        errors = {}

        if self.approver_kind == self.ApproverKind.EMPLOYEE and not self.approver_employee:
            errors["approver_employee"] = "يجب تحديد الموظف الموافق عند اختيار نوع Employee."

        if self.approver_kind == self.ApproverKind.GROUP and not self.approver_group:
            errors["approver_group"] = "يجب تحديد المجموعة/الدور عند اختيار نوع Group."

        if self.approver_kind != self.ApproverKind.MANAGER_CHAIN and self.manager_level != 1:
            # لتفادي إدخالات مربكة
            errors["manager_level"] = "manager_level يُستخدم فقط مع MANAGER_CHAIN."

        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return f"{self.evaluation_type.name} → {self.name} ({self.approver_kind})"


# ------------------------------------------------------------
# Evaluation Template / Parameters / Results
# ------------------------------------------------------------
class EvaluationTemplate( TimeStampedMixin, UserStampedMixin, ActivableMixin):
    """
    قالب تقييم رسمي (مثال: Call Center Q1 Form) يُستَخدم لبناء تقييمات لموظفين.
    يدعم:
    - ربطه بنوع تقييم EvaluationType
    - رقم إصدار (version) لتمييز النسخ عبر السنوات/الدورات
    - حالة تجميد (is_locked) عند استخدامه فعلياً في Evaluations
    """

    company = models.ForeignKey("base.Company", on_delete=models.PROTECT, related_name="evaluation_templates")

    evaluation_type = models.ForeignKey(
        "performance.EvaluationType",
        on_delete=models.PROTECT,
        related_name="templates",
        null=True,
        blank=True,
    )

    name        = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    active      = models.BooleanField(default=True)

    # رقم الإصدار: يساعد على تمييز النسخ المختلفة من نفس القالب (مثلاً سنوي 2024، سنوي 2025)
    version = models.PositiveIntegerField(
        default=1,
        help_text="رقم إصدار القالب لتمييز النسخ المختلفة عبر السنوات/الدورات."
    )

    # تجميد القالب: إذا أصبح مستخدماً في Evaluations فعلية نمنع تعديل البنية/المعاملات
    is_locked = models.BooleanField(
        default=False,
        help_text=(
            "إذا كان القالب مستخدماً في تقييمات فعلية يتم تجميده، "
            "ولا يُسمح بتعديل معاملاته أو هيكله الأساسي للحفاظ على عدالة التقييمات التاريخية."
        ),
    )

    @property
    def total_weight_pct(self) -> int:
        """
        مجموع أوزان جميع EvaluationParameter المرتبطة بهذا القالب.
        نستخدمه لضمان أن توزيع الأوزان = 100% لضمان عدالة ووضوح النتيجة النهائية.
        """
        return sum(p.weight_pct or 0 for p in self.parameters.all())

    def clean(self):
        """
        التحقق من:
        1) أن مجموع الأوزان داخل القالب = 100% (إذا كان هناك Parameters)
           - إذا كان > 100% قد نحصل على درجات نهائية تتجاوز 100%.
           - إذا كان < 100% لن يستطيع الموظف الوصول إلى 100% حتى لو أخذ أعلى درجة في كل بند.
        2) منع فكّ تجميد قالب مستخدم في Evaluations (لا يُسمح بتحويل is_locked من True إلى False إذا كان هناك تقييمات).
        """
        super().clean()

        # 1) التحقق من مجموع الأوزان
        total = self.total_weight_pct
        if self.parameters.exists() and total != 100:
            raise ValidationError(
                {
                    "__all__": (
                        f"Total weight of parameters must be 100%, got {total}%. "
                        "يرجى تعديل أوزان EvaluationParameter داخل هذا القالب ليكون مجموعها 100%."
                    )
                }
            )

        # 2) منع فكّ تجميد قالب تم استخدامه فعلياً
        if self.pk and not self.is_locked:
            # إذا كانت هناك Evaluations مرتبطة بهذا القالب، لا نسمح بإلغاء التجميد
            if self.evaluations.exists():
                raise ValidationError(
                    {
                        "is_locked": (
                            "لا يمكن إلغاء تجميد قالب تم استخدامه في Evaluations فعلية. "
                            "فضلاً أنشئ إصداراً جديداً (version جديد) إذا أردت تغيير النموذج."
                        )
                    }
                )



    class Meta:
        db_table = "perf_evaluation_template"
        unique_together = [("company", "name")]
        ordering = ["company", "name"]
        permissions = [
            ("use_evaluation_template", "Can use evaluation template"),
            ("manage_template_parameters", "Can manage template parameters"),
        ]

    def __str__(self):
        # نضمّن رقم الإصدار في الاسم لسهولة التمييز في واجهة الإدارة
        return f"{self.name} (v{self.version})"


class EvaluationParameter( TimeStampedMixin, UserStampedMixin):
    """
    صف/معامل داخل القالب.
    يدعم مصادر متعددة: Objective/KPI/Tasks/External/Manual.
    """


    class SourceKind(models.TextChoices):
        OBJECTIVE_SCORE   = "objective_score", "Objective Score (score_pct)"
        OBJECTIVE_PROGRESS = "objective_progress", "Objective Progress (progress_pct)"
        KPI_SCORE         = "kpi_score", "KPI Score (score_pct)"
        TASKS_PROGRESS    = "tasks_progress", "Tasks Progress (avg % complete)"
        EXTERNAL_METRIC   = "external_metric", "External Metric (model/field/filter)"
        MANUAL            = "manual", "Manual Entry (default)"
        DAILY_RATING = "daily_rating", "Daily Rating (avg overall score)"
        TEMP_TASKS_LOAD = "temp_tasks_load", "Temporary Tasks Load Index"
        TEMP_TASKS_SCORE = "temp_tasks_score", "Temporary Tasks Performance Score"
        EMPLOYEE_OBJECTIVE_SCORE = "employee_objective_score", "Employee Objective Contribution Score"
        EMPLOYEE_OBJECTIVE_TIMELINESS = (
            "employee_objective_timeliness",
            "Employee Objective Timeliness (Tasks Due/Done)",
        )
        EMPLOYEE_OBJECTIVE_EFFICIENCY = (
            "employee_objective_efficiency",
            "Employee Objective Time Efficiency",
        )
        EMPLOYEE_OBJECTIVE_QUALITY = (
            "employee_objective_quality",
            "Employee Objective Tasks Quality",
        )
        QUALITY_SCORE = "quality_score", "Quality / Mistakes / Complaints Score"
        FEEDBACK_SCORE = "feedback_score", "360° Feedback (Self/Manager/Peers)"

    template = models.ForeignKey("performance.EvaluationTemplate", on_delete=models.CASCADE, related_name="parameters")
    name     = models.CharField(max_length=255)
    code     = models.CharField(max_length=64, blank=True)
    weight_pct = models.PositiveIntegerField(help_text="0..100")

    source_kind = models.CharField(max_length=32, choices=SourceKind.choices, default=SourceKind.MANUAL)

    # روابط مؤشّرات/أهداف (عند الحاجة)
    objective = models.ForeignKey("performance.Objective", null=True, blank=True, on_delete=models.SET_NULL, related_name="eval_params")
    kpi       = models.ForeignKey("performance.KPI",       null=True, blank=True, on_delete=models.SET_NULL, related_name="eval_params")

    # مصدر خارجي عام (model.field + agg + فلتر JSON مع placeholders)
    external_model       = models.CharField(max_length=128, blank=True, help_text="e.g. 'attendance.AttendanceLog'")
    external_field       = models.CharField(max_length=64, blank=True, help_text="Field to aggregate (e.g., 'worked_minutes')")
    external_aggregation = models.CharField(max_length=16, blank=True, choices=[("sum","Sum"),("avg","Average"),("latest","Latest")], default="", help_text="How to combine values")
    external_filter      = models.JSONField(default=dict, blank=True, help_text="Optional filter JSON (key->value)")

    # قيم يدوية/حدود قصّ للنتيجة
    manual_default_score_pct = models.PositiveIntegerField(default=0, help_text="Default 0..100")
    min_score_pct            = models.PositiveIntegerField(default=0)
    max_score_pct            = models.PositiveIntegerField(default=100)

    def clean(self):
        super().clean()
        # نضمن أن المصدر (Objective/KPI) يتبع نفس شركة القالب
        if self.objective and self.objective.company_id != self.template.company_id:
            raise ValidationError({"objective": "Objective must belong to the same company as the Template."})
        if self.kpi and self.kpi.company_id != self.template.company_id:
            raise ValidationError({"kpi": "KPI must belong to the same company as the Template."})

    class Meta:
        db_table = "perf_evaluation_parameter"
        ordering = ["template", "name"]
        constraints = [
            # الوزن
            models.CheckConstraint(
                check=models.Q(weight_pct__gte=0, weight_pct__lte=100),
                name="chk_param_weight_0_100_v2",
            ),
            models.CheckConstraint(
                check=models.Q(min_score_pct__gte=0, min_score_pct__lte=100),
                name="chk_param_min_0_100",
            ),
            models.CheckConstraint(
                check=models.Q(max_score_pct__gte=0, max_score_pct__lte=100),
                name="chk_param_max_0_100",
            ),
            models.CheckConstraint(
                check=models.Q(min_score_pct__lte=models.F("max_score_pct")),
                name="chk_param_min_le_max",
            ),
            models.UniqueConstraint(
                fields=["template", "code"],
                name="perf_param_template_code_uniq_v2",
                condition=~models.Q(code=""),
            ),
        ]

        permissions = [("reorder_parameters", "Can reorder evaluation parameters")]

    def __str__(self):
        return f"{self.template.name}: {self.name} ({self.weight_pct}%)"


class EvaluationParameterResult( TimeStampedMixin, UserStampedMixin):
    """
    نتيجة مُحتسبة لمعامل واحد ضمن تقييم معيّن.
    - raw_value: قيمة المصدر (رقم/JSON)
    - score_pct: قيمة 0..100 بعد القصّ
    """

    

    evaluation = models.ForeignKey("performance.Evaluation",        on_delete=models.CASCADE, related_name="parameter_results")
    parameter  = models.ForeignKey("performance.EvaluationParameter", on_delete=models.CASCADE, related_name="results")

    raw_value_number = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    raw_value_json   = models.JSONField(null=True, blank=True)
    score_pct        = models.PositiveIntegerField(default=0)

    def clean(self):
        super().clean()
        # parameter.template يجب أن يطابق evaluation.template (نفس القالب)
        if self.parameter and self.evaluation and self.parameter.template_id != self.evaluation.template_id:
            raise ValidationError({"parameter": "Parameter must belong to the same template as the Evaluation."})

        # كما نضمن اتساق الشركة عبر (evaluation.company == parameter.template.company)
        if self.parameter and self.evaluation and self.parameter.template.company_id != self.evaluation.company_id:
            raise ValidationError({"parameter": "Parameter's Template company must match the Evaluation company."})

    class Meta:
        db_table = "perf_evaluation_parameter_result"
        unique_together = [("evaluation", "parameter")]
        indexes = [models.Index(fields=["evaluation", "parameter"])]
        permissions = [("rate_parameter_result", "Can rate parameter result")]
        constraints = [
            models.CheckConstraint(
                check=models.Q(score_pct__gte=0, score_pct__lte=100),
                name="chk_param_result_score_0_100",
            ),
        ]

    def __str__(self):
        return f"{self.evaluation} · {self.parameter.name}: {self.score_pct}%"


# --------------------------------------------------
# Evaluation , QualityIncident , EvaluationFeedback
# --------------------------------------------------

class QualityIncident(TimeStampedMixin, UserStampedMixin, CompanyOwnedMixin, models.Model):
    """
    Represents a quality issue or customer complaint affecting employee evaluation.
    """

    SEVERITY = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("critical", "Critical"),
    ]

    employee = models.ForeignKey(
        "hr.Employee",
        on_delete=models.CASCADE,
        related_name="quality_incidents"
    )

    date = models.DateField()

    severity = models.CharField(
        max_length=16,
        choices=SEVERITY,
        default="medium",
    )

    impact_score_pct = models.PositiveIntegerField(
        default=100,
        help_text="0..100: higher means better handling, lower means worse"
    )

    description = models.TextField(blank=True)

    class Meta:
        db_table = "perf_quality_incident"
        ordering = ["-date"]

    def __str__(self):
        return f"{self.employee} — {self.severity} — {self.impact_score_pct}"


class EvaluationFeedback(TimeStampedMixin, UserStampedMixin, CompanyOwnedMixin, models.Model):
    """
    360° feedback مرتبط بتقييم واحد (Evaluation).
    يمكن أن يكون من:
      - الموظف نفسه (self)
      - المدير المباشر (manager)
      - زميل (peer)
      - مدير أعلى (skip_manager)
      - HR
    """

    class Role(models.TextChoices):
        SELF = "self", "Self"
        MANAGER = "manager", "Direct Manager"
        PEER = "peer", "Peer / Colleague"
        SKIP_MANAGER = "skip_manager", "Skip-level Manager"
        HR = "hr", "HR"
        OTHER = "other", "Other"

    evaluation = models.ForeignKey(
        "performance.Evaluation",
        on_delete=models.CASCADE,
        related_name="feedbacks",
    )

    from_employee = models.ForeignKey(
        "hr.Employee",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="given_feedbacks",
        help_text="Employee giving the feedback (if applicable).",
    )

    role = models.CharField(
        max_length=16,
        choices=Role.choices,
        default=Role.MANAGER,
    )

    overall_score_pct = models.PositiveIntegerField(
        default=0,
        help_text="Overall feedback score (0..100).",
    )

    comment = models.TextField(blank=True)

    class Meta:
        db_table = "perf_evaluation_feedback"
        ordering = ["evaluation", "-created_at"]

    def __str__(self):
        return f"{self.evaluation} – {self.role} – {self.overall_score_pct}%"


class Evaluation( CompanyOwnedMixin, TimeStampedMixin, UserStampedMixin, ActivableMixin):
    """
    تقييم نهاية فترة لموظّف، مرتبط بقالب، ويُنتج نتائج معاملات ودرجة نهائية.
    - الآن يدعم Workflow كامل مبني على EvaluationType + EvaluationApprovalStep
    """

    # ---------------- Basic Core Fields ----------------
    company   = models.ForeignKey("base.Company", on_delete=models.PROTECT, related_name="evaluations")
    employee  = models.ForeignKey("hr.Employee",  on_delete=models.PROTECT, related_name="evaluations")
    evaluator = models.ForeignKey("hr.Employee",  null=True, blank=True, on_delete=models.SET_NULL, related_name="given_evaluations")

    date_start = models.DateField()
    date_end   = models.DateField()

    template = models.ForeignKey(
        "performance.EvaluationTemplate",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="evaluations",
    )

    evaluation_type = models.ForeignKey(
        "performance.EvaluationType",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="evaluations",
        help_text="نوع التقييم (شهري، ربع سنوي، سنوي، أو حسب ما تُعرّفه من الـ Admin).",
    )

    overall_rating    = models.CharField(max_length=32, blank=True)
    calibration_notes = models.TextField(blank=True)

    final_score_pct = models.PositiveIntegerField(default=0, db_index=True)

    # -------------------------------------------------
    # حقول المعايرة (Calibration)
    # -------------------------------------------------
    calibrated_score_pct = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Final calibrated score (0..100). If null, use final_score_pct."
    )

    calibration_reason = models.TextField(
        blank=True,
        help_text="Reason for calibration / normalization."
    )

    calibration_applied_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When calibration was applied."
    )

    calibration_applied_by = models.ForeignKey(
        "hr.Employee",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="applied_evaluation_calibrations",
        help_text="Who applied the calibration (usually manager/HR)."
    )


    # ---------------- Workflow State Machine ----------------
    STATE = [
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("in_progress", "In Progress"),   # مضافة حديثاً
        ("calibrated", "Calibrated"),
        ("approved", "Approved"),
        ("locked", "Locked"),
    ]
    state = models.CharField(max_length=12, choices=STATE, default="draft", db_index=True)

    # ---------------- Workflow Tracking ----------------
    # رقم الخطوة الحالية
    current_step = models.PositiveIntegerField(default=0, help_text="الخطوة الحالية داخل Workflow.")

    # المراجع الحالي (Approver) الذي بيده القرار الآن
    current_approver = models.ForeignKey(
        "hr.Employee",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="evaluations_pending_approval",
        help_text="الموظف المطلوب منه اعتماد الخطوة الحالية.",
    )

    # ---------------- Action Timestamps ----------------
    submitted_at = models.DateTimeField(null=True, blank=True)
    submitted_by = models.ForeignKey("hr.Employee", null=True, blank=True, on_delete=models.SET_NULL, related_name="submitted_evaluations")

    calibrated_at = models.DateTimeField(null=True, blank=True)
    calibrated_by = models.ForeignKey("hr.Employee", null=True, blank=True, on_delete=models.SET_NULL, related_name="calibrated_evaluations")

    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey("hr.Employee", null=True, blank=True, on_delete=models.SET_NULL, related_name="approved_evaluations")

    locked_at = models.DateTimeField(null=True, blank=True)

    @property
    def is_locked(self) -> bool:
        return self.state in ("approved", "locked") or bool(self.locked_at)


    class Meta:
        db_table = "perf_evaluation"
        indexes = [
            models.Index(fields=["company", "employee", "date_start", "date_end"]),
            models.Index(fields=["state", "date_end"], name="eval_state_idx"),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(date_start__lte=models.F("date_end")), name="chk_eval_dates"),
            models.UniqueConstraint(fields=["employee", "date_start", "date_end"], name="uniq_eval_employee_period"),
            models.CheckConstraint(
                check=models.Q(final_score_pct__gte=0, final_score_pct__lte=100),
                name="chk_eval_final_0_100",
            ),
        ]
        permissions = [
            ("submit_evaluation", "Can submit evaluation"),
            ("calibrate_evaluation", "Can calibrate evaluation"),
            ("approve_evaluation", "Can approve evaluation"),
            ("lock_evaluation", "Can lock evaluation"),
            ("view_confidential_notes", "Can view confidential evaluation notes"),
        ]

    def __str__(self):
        return f"Evaluation {self.employee.name} [{self.date_start} → {self.date_end}]"

    # ---------------- Validation ----------------
    def clean(self):
        super().clean()

        # Company consistency
        if self.employee and self.company and self.employee.company_id != self.company_id:
            raise ValidationError({"employee": "Employee must belong to the same company."})

        if self.template and self.template.company_id != self.company_id:
            raise ValidationError({"template": "Template must belong to the same company."})

        if self.evaluator and self.evaluator.company_id != self.company_id:
            raise ValidationError({"evaluator": "Evaluator must belong to the same company."})

        if self.submitted_by and self.submitted_by.company_id != self.company_id:
            raise ValidationError({"submitted_by": "Submitted-by must belong to the same company."})

        if self.calibrated_by and self.calibrated_by.company_id != self.company_id:
            raise ValidationError({"calibrated_by": "Calibrated-by must belong to the same company."})

        if self.approved_by and self.approved_by.company_id != self.company_id:
            raise ValidationError({"approved_by": "Approved-by must belong to the same company."})

        # ------------------------------------------------
        # NEW VALIDATION: Ensure template matches evaluation_type
        # ------------------------------------------------
        if self.template and self.evaluation_type:
            # إذا كان الـ Template مرتبطاً بنوع معين، يجب أن يتطابق مع نوع التقييم
            if self.template.evaluation_type_id and self.template.evaluation_type_id != self.evaluation_type_id:
                raise ValidationError({
                    "template": "Selected EvaluationTemplate does not match the chosen EvaluationType."
                })


    # ============================================================
    #  Scoring Engine (unchanged)
    # ============================================================
    def _external_metric(self, param):
        from performance import services  # LAZY IMPORT

        adapter = services.get_adapter(param.code) if param.code else None

        ctx = {
            "employee_id": self.employee_id,
            "company_id": self.company_id,
            "date_start": self.date_start,
            "date_end": self.date_end,
        }

        if adapter:
            return adapter(context=ctx, param=param)

        generic = services.get_adapter("generic_model")
        if not generic:
            return None, {"error": "no_generic_adapter"}

        if not (param.external_model and param.external_field and param.external_aggregation):
            return None, None

        return generic(
            app_model=param.external_model,
            field=param.external_field,
            aggregation=param.external_aggregation,
            filter_json=param.external_filter or {},
            context=ctx,
        )

    def _clamp(self, v, lo, hi) -> int:
        from performance import services  # LAZY IMPORT
        return services.clamp_to_pct(v, lo, hi)

    def _objective_applies_to_employee(self, obj) -> bool:
        from performance import services  # LAZY IMPORT
        return services.objective_applies(self, obj)

    def _avg_task_progress(self, objective) -> int:
        from performance import services  # LAZY IMPORT
        return services.avg_task_progress_for(self, objective)

    @transaction.atomic
    def recompute(self):
        """
        إعادة حساب:
          - نتائج EvaluationParameterResult لكل Parameter في الـ Template
          - الدرجة النهائية final_score_pct
          - تأثير الاستثناءات PerformanceException
        """

        # ملاحظة مهمة:
        # هذه الدالة تحسب final_score_pct (النتيجة الآلية) فقط.
        # لا تقوم بتعديل حقول المعايرة (calibrated_score_pct, ...).
        # أي معايرة تتم من خلال EvaluationCalibration أو عبر واجهة الإدارة.

        from performance.models import (
            EvaluationParameter,
            EvaluationParameterResult,
            DailyRating,
            Task,
            PerformanceException,
            EvaluationExceptionAdjustment,
            EmployeeObjectiveScore,
        )
        from performance import services as svc

        EP = EvaluationParameter
        SPR = EvaluationParameterResult

        # نحذف النتائج القديمة
        self.parameter_results.all().delete()

        params = EP.objects.filter(template=self.template).order_by("id")

        total_weight = 0
        weighted_sum = 0

        # ------------------------------------------------------------
        # 1. حساب نتائج كل EvaluationParameterResult
        # ------------------------------------------------------------
        for p in params:
            raw_number = None
            raw_json = None
            score = p.manual_default_score_pct or 0

            min_s = p.min_score_pct if p.min_score_pct is not None else 0
            max_s = p.max_score_pct if p.max_score_pct is not None else 100

            # --------------------------
            # MANUAL
            # --------------------------
            if p.source_kind == EP.SourceKind.MANUAL:
                score = p.manual_default_score_pct or 0

            # --------------------------
            # OBJECTIVE_SCORE
            # --------------------------
            elif p.source_kind == EP.SourceKind.OBJECTIVE_SCORE:
                obj = p.objective
                if obj and svc.objective_applies(self, obj):
                    raw_number = obj.score_pct
                    score = raw_number

            # --------------------------
            # OBJECTIVE_PROGRESS
            # --------------------------
            elif p.source_kind == EP.SourceKind.OBJECTIVE_PROGRESS:
                obj = p.objective
                if obj and svc.objective_applies(self, obj):
                    raw_number = obj.progress_pct
                    score = raw_number

            # --------------------------
            # KPI_SCORE
            # --------------------------
            elif p.source_kind == EP.SourceKind.KPI_SCORE:
                kpi = p.kpi
                if (
                    kpi
                    and kpi.company_id == self.company_id
                    and kpi.objective
                    and svc.objective_applies(self, kpi.objective)
                ):
                    raw_number = kpi.score_pct
                    score = raw_number

            # --------------------------
            # TASKS_PROGRESS
            # --------------------------
            elif p.source_kind == EP.SourceKind.TASKS_PROGRESS:
                obj = p.objective
                if obj and svc.objective_applies(self, obj):
                    raw_number = svc.avg_task_progress_for(self, obj)
                    score = raw_number

            # --------------------------
            # DAILY_RATING
            # --------------------------
            elif p.source_kind == EP.SourceKind.DAILY_RATING:
                qs = DailyRating.objects.filter(
                    employee=self.employee,
                    company=self.company,
                    date__range=(self.date_start, self.date_end),
                )
                if qs.exists():
                    raw_number = sum(r.overall_score_pct for r in qs) / qs.count()
                    score = int(round(raw_number))

            # --------------------------
            # TEMP_TASKS_LOAD
            # --------------------------
            elif p.source_kind == EP.SourceKind.TEMP_TASKS_LOAD:
                qs = Task.objects.filter(
                    company=self.company,
                    assignee=self.employee,
                    due_date__range=(self.date_start, self.date_end),
                ).exclude(status__in=["cancelled"])

                temp_qs = qs.filter(task_kind="temporary")
                non_temp_qs = qs.exclude(task_kind="temporary")

                def _total_effort(q):
                    return sum(t.actual_minutes or t.estimated_minutes for t in q)

                temp_effort = _total_effort(temp_qs)
                planned_effort = _total_effort(non_temp_qs)

                if temp_effort + planned_effort == 0:
                    raw_number = None
                    score = p.manual_default_score_pct or 0
                else:
                    raw_number = (temp_effort / (temp_effort + planned_effort)) * 100.0
                    score = int(round(raw_number))

            # --------------------------
            # TEMP_TASKS_SCORE
            # --------------------------
            elif p.source_kind == EP.SourceKind.TEMP_TASKS_SCORE:
                qs = Task.objects.filter(
                    company=self.company,
                    assignee=self.employee,
                    due_date__range=(self.date_start, self.date_end),
                    task_kind="temporary",
                ).exclude(status__in=["cancelled"])

                if not qs.exists():
                    raw_number = None
                    score = p.manual_default_score_pct or 0
                else:
                    PRIORITY_WEIGHTS = {
                        "critical": 3.0,
                        "high": 2.0,
                        "normal": 1.0,
                        "low": 0.5,
                    }

                    weighted_sum_temp = 0.0
                    total_weight_temp = 0.0

                    for t in qs:
                        w = PRIORITY_WEIGHTS.get(getattr(t, "priority", "normal"), 1.0)
                        eff = (t.actual_minutes or t.estimated_minutes or 30)
                        item_weight = w * eff
                        total_weight_temp += item_weight

                        q_score = t.quality_score_pct or t.percent_complete
                        weighted_sum_temp += q_score * item_weight

                    if total_weight_temp == 0:
                        raw_number = None
                        score = p.manual_default_score_pct or 0
                    else:
                        raw_number = weighted_sum_temp / total_weight_temp
                        score = int(round(raw_number))


            # ----------------------------------------
            # QUALITY_SCORE
            # ----------------------------------------
            elif p.source_kind == EP.SourceKind.QUALITY_SCORE:
                from performance.models import QualityIncident

                incidents = QualityIncident.objects.filter(
                    company=self.company,
                    employee=self.employee,
                    date__range=(self.date_start, self.date_end),
                )

                if not incidents.exists():
                    raw_number = 100
                    score = 100
                else:
                    SEVERITY_WEIGHTS = {
                        "critical": 3.0,
                        "high": 2.0,
                        "medium": 1.5,
                        "low": 1.0,
                    }

                    penalty = 0.0

                    for inc in incidents:
                        sev_w = SEVERITY_WEIGHTS.get(inc.severity, 1.0)
                        penalty += sev_w * (100 - inc.impact_score_pct)

                    # لا يمكن أن يزيد العقاب عن 100
                    penalty = min(penalty, 100)

                    raw_number = max(0, 100 - penalty)
                    score = int(round(raw_number))


            # ----------------------------------------
            # EMPLOYEE_OBJECTIVE_SCORE (جديد)
            # ----------------------------------------
            elif p.source_kind == EP.SourceKind.EMPLOYEE_OBJECTIVE_SCORE:
                obj = p.objective
                if obj:
                    eos = EmployeeObjectiveScore.objects.filter(
                        employee=self.employee,
                        objective=obj,
                    ).first()
                    if eos:
                        raw_number = eos.final_score_pct
                        score = eos.final_score_pct
                    else:
                        raw_number = None
                        score = p.manual_default_score_pct or 0

            # ----------------------------------------
            # EMPLOYEE_OBJECTIVE_TIMELINESS
            # ----------------------------------------
            elif p.source_kind == EP.SourceKind.EMPLOYEE_OBJECTIVE_TIMELINESS:
                obj = p.objective
                if obj:
                    eos = EmployeeObjectiveScore.objects.filter(
                        employee=self.employee,
                        objective=obj,
                    ).first()
                    if eos:
                        raw_number = eos.timeliness_pct
                        score = eos.timeliness_pct
                    else:
                        raw_number = None
                        score = p.manual_default_score_pct or 0

            # ----------------------------------------
            # EMPLOYEE_OBJECTIVE_EFFICIENCY
            # ----------------------------------------
            elif p.source_kind == EP.SourceKind.EMPLOYEE_OBJECTIVE_EFFICIENCY:
                obj = p.objective
                if obj:
                    eos = EmployeeObjectiveScore.objects.filter(
                        employee=self.employee,
                        objective=obj,
                    ).first()
                    if eos:
                        raw_number = eos.efficiency_pct
                        score = eos.efficiency_pct
                    else:
                        raw_number = None
                        score = p.manual_default_score_pct or 0

            # ----------------------------------------
            # EMPLOYEE_OBJECTIVE_QUALITY
            # ----------------------------------------
            elif p.source_kind == EP.SourceKind.EMPLOYEE_OBJECTIVE_QUALITY:
                obj = p.objective
                if obj:
                    eos = EmployeeObjectiveScore.objects.filter(
                        employee=self.employee,
                        objective=obj,
                    ).first()
                    if eos:
                        raw_number = eos.quality_pct
                        score = eos.quality_pct
                    else:
                        raw_number = None
                        score = p.manual_default_score_pct or 0


            # ----------------------------------------
            # FEEDBACK_SCORE (360° Feedback)
            # ----------------------------------------
            elif p.source_kind == EP.SourceKind.FEEDBACK_SCORE:
                # نقرأ كل الـ feedbacks المرتبطة بهذا الـ evaluation
                fqs = self.feedbacks.select_related("evaluation").all()

                if not fqs.exists():
                    raw_number = None
                    score = p.manual_default_score_pct or 0
                else:
                    # أوزان الأدوار المختلفة (يمكن تعديلها لاحقاً حسب سياسة الشركة)
                    ROLE_WEIGHTS = {
                        "self": 1.0,
                        "peer": 1.5,
                        "manager": 3.0,
                        "skip_manager": 2.5,
                        "hr": 2.0,
                        "other": 1.0,
                    }

                    weighted_sum_fb = 0.0
                    total_weight_fb = 0.0

                    for fb in fqs:
                        w = ROLE_WEIGHTS.get(fb.role, 1.0)
                        total_weight_fb += w
                        weighted_sum_fb += fb.overall_score_pct * w

                    if total_weight_fb == 0:
                        raw_number = None
                        score = p.manual_default_score_pct or 0
                    else:
                        raw_number = weighted_sum_fb / total_weight_fb
                        score = int(round(raw_number))


            # --------------------------
            # EXTERNAL_METRIC
            # --------------------------
            elif p.source_kind == EP.SourceKind.EXTERNAL_METRIC:
                adapter = svc.get_adapter("generic_model")
                if adapter and p.external_model and p.external_field:
                    ctx = {
                        "employee_id": self.employee_id,
                        "company_id": self.company_id,
                        "date_start": self.date_start,
                        "date_end": self.date_end,
                    }
                    raw_number, extra = adapter(
                        app_model=p.external_model,
                        field=p.external_field,
                        aggregation=p.external_aggregation or "avg",
                        filter_json=p.external_filter or {},
                        context=ctx,
                    )
                    raw_json = extra
                    if raw_number is not None:
                        score = svc.clamp_to_pct(raw_number, min_s, max_s)

            # --------------------------
            # ضبط score ضمن min/max
            # --------------------------
            if p.source_kind != EP.SourceKind.EXTERNAL_METRIC:
                score = svc.clamp_to_pct(score, min_s, max_s)

            # --------------------------
            # إنشاء EvaluationParameterResult
            # --------------------------
            SPR.objects.create(
                evaluation=self,
                parameter=p,
                raw_value_number=raw_number,
                raw_value_json=raw_json,
                score_pct=score,
            )

            # تجميع final score
            w = p.weight_pct or 0
            total_weight += w
            weighted_sum += score * w

        # ------------------------------------------------------------
        # 2. حساب الدرجة الأساسية قبل الاستثناءات
        # ------------------------------------------------------------
        if total_weight > 0:
            base_score = int(round(weighted_sum / total_weight))
        else:
            base_score = 0

        self.final_score_pct = base_score

        # ------------------------------------------------------------
        # 3. حساب تأثير الاستثناءات (PerformanceException)
        # ------------------------------------------------------------
        self.exception_adjustments.all().delete()

        exceptions = PerformanceException.objects.filter(
            employee=self.employee,
            company=self.company,
            date_start__lte=self.date_end,
            date_end__gte=self.date_start,
        )

        exception_total = 0.0

        for exc in exceptions:
            # multiplier: impact_pct أو type.multiplier
            multiplier = exc.impact_pct if exc.impact_pct is not None else exc.type.multiplier

            # enforce is_positive
            if exc.type.is_positive and multiplier < 0:
                multiplier = abs(multiplier)
            if not exc.type.is_positive and multiplier > 0:
                multiplier = -abs(multiplier)

            # enforce max_impact_pct
            max_pct = (exc.type.max_impact_pct or 100) / 100.0
            if abs(multiplier) > max_pct:
                multiplier = max_pct if multiplier > 0 else -max_pct

            impact = base_score * multiplier

            EvaluationExceptionAdjustment.objects.create(
                evaluation=self,
                exception=exc,
                adjustment_pct=impact,
            )

            exception_total += impact

        # تطبيق تأثير الاستثناءات
        self.final_score_pct = int(round(base_score + exception_total))
        self.final_score_pct = max(0, min(100, self.final_score_pct))

        return self

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_locked:
            return
        self.recompute()
        super().save(update_fields=["final_score_pct"])

    # ============================================================
    # Workflow Methods (NEW)
    # ============================================================
    def _get_steps(self):
        """إرجاع الخطوات المرتبطة بنوع التقييم بالترتيب."""
        if not self.evaluation_type:
            return []
        return list(self.evaluation_type.approval_steps.filter(active=True).order_by("sequence"))

    def _resolve_approver(self, step):
        """
        إرجاع الموظف الذي يجب أن يعتمد الخطوة الحالية.
        """
        kind = step.approver_kind

        if kind == step.ApproverKind.EMPLOYEE:
            return step.approver_employee

        if kind == step.ApproverKind.GROUP:
            # موافقة أي عضو في الـ Group مقبولة
            return None  # يتم التحقق لاحقًا في approve_step()

        if kind == step.ApproverKind.DIRECT_MANAGER:
            return self.employee.manager

        if kind == step.ApproverKind.DEPARTMENT_MANAGER:
            return self.employee.department.manager if self.employee.department else None

        if kind == step.ApproverKind.MANAGER_CHAIN:
            emp = self.employee
            for _ in range(step.manager_level):
                if not emp or not emp.manager:
                    return None
                emp = emp.manager
            return emp

        return None

    def start_workflow(self):
        """تشغيل الخطوات لأول مرة عند submit."""
        steps = self._get_steps()
        if not steps:
            return

        self.current_step = 1
        step = steps[0]
        self.current_approver = self._resolve_approver(step)
        self.state = "in_progress"
        self.save(update_fields=["current_step", "current_approver", "state"])

    def approve_step(self, by_employee):
        """
        موافقة على الخطوة الحالية.
        """
        steps = self._get_steps()
        if not steps:
            return

        step_index = self.current_step - 1
        if step_index < 0 or step_index >= len(steps):
            return

        step = steps[step_index]

        # إذا نوع الموافقة GROUP → يكفي موظف واحد فقط من المجموعة
        if step.approver_kind == step.ApproverKind.GROUP:
            if not by_employee.user.groups.filter(id=step.approver_group_id).exists():
                return  # ليس من ضمن المجموعة
        else:
            # موافق واحد فقط
            if self.current_approver_id and self.current_approver_id != by_employee.id:
                return

        # ننتقل إلى الخطوة التالية
        if self.current_step < len(steps):
            self.current_step += 1
            next_step = steps[self.current_step - 1]
            self.current_approver = self._resolve_approver(next_step)
            self.state = "in_progress"
            self.save(update_fields=["current_step", "current_approver", "state"])
            return

        # آخر خطوة → اعتماد نهائي
        self.state = "approved"
        self.approved_at = timezone.now()
        self.approved_by = by_employee
        self.save(update_fields=["state", "approved_at", "approved_by"])

    def reject_step(self, by_employee):
        """
        رفض الخطوة الحالية → العودة خطوة للخلف حسب المطلوب.
        """
        if self.current_step <= 1:
            # العودة للموظف
            self.current_step = 0
            self.current_approver = None
            self.state = "submitted"
            self.save(update_fields=["current_step", "current_approver", "state"])
            return

        # العودة للخطوة السابقة
        steps = self._get_steps()
        prev_index = self.current_step - 2
        prev_step = steps[prev_index]

        self.current_step -= 1
        self.current_approver = self._resolve_approver(prev_step)
        self.state = "in_progress"
        self.save(update_fields=["current_step", "current_approver", "state"])

    # -------- Original State Transitions (unchanged logic) --------
    def submit(self, by=None):
        if self.state != "draft":
            return
        self.state = "submitted"
        self.submitted_at = timezone.now()
        if by:
            self.submitted_by = by
        self.recompute()
        super().save(update_fields=["state", "submitted_at", "submitted_by", "final_score_pct"])
        self.start_workflow()

    def calibrate(self, by=None):
        if self.state not in ("submitted", "in_progress", "calibrated"):
            return
        self.state = "calibrated"
        self.calibrated_at = timezone.now()
        if by:
            self.calibrated_by = by
        self.recompute()
        super().save(update_fields=["state", "calibrated_at", "calibrated_by", "final_score_pct"])

    def approve(self, by=None):
        """
        موافقة قديمة (تبقى موجودة للـ API أو الـ Admin)
        لكنها تُستبدل الآن بـ approve_step().
        """
        if by:
            self.approve_step(by)

    def lock(self):
        if self.state in ("approved", "locked"):
            self.state = "locked"
            self.locked_at = timezone.now()
            super().save(update_fields=["state", "locked_at"])

    @property
    def effective_score_pct(self) -> int:
        """
        الدرجة الفعلية المعتمدة للتقرير:
          - إذا كانت calibrated_score_pct موجودة → نستخدمها
          - وإلا نستخدم final_score_pct (النتيجة الآلية)
        """
        return self.calibrated_score_pct if self.calibrated_score_pct is not None else self.final_score_pct


# -------------------------------------------------------------------------
# EvaluationCalibration , DailyRatingFactor , DailyRating , DailyRatingItem
# -------------------------------------------------------------------------

class EvaluationCalibration(TimeStampedMixin, UserStampedMixin, CompanyOwnedMixin, models.Model):
    """
    يمثل عملية معايرة واحدة (Calibration) لتقييم معين.
    يخزن:
      - الدرجة الأصلية قبل المعايرة
      - الدرجة الجديدة بعد المعايرة
      - السبب
      - من قام بالمعايرة
    """

    evaluation = models.ForeignKey(
        "performance.Evaluation",
        on_delete=models.CASCADE,
        related_name="calibrations",
    )

    old_score_pct = models.PositiveIntegerField(
        help_text="Evaluation final_score_pct before calibration."
    )

    new_score_pct = models.PositiveIntegerField(
        help_text="Calibrated score (0..100)."
    )

    reason = models.TextField(blank=True)

    applied_by = models.ForeignKey(
        "hr.Employee",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="evaluation_calibrations",
    )

    class Meta:
        db_table = "perf_evaluation_calibration"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Eval #{self.evaluation.id}: {self.old_score_pct} → {self.new_score_pct}"

    def save(self, *args, **kwargs):
        """
        عند حفظ معايرة جديدة، يتم تحديث حقول المعايرة في Evaluation المرتبط.
        """
        creating = self.pk is None
        super().save(*args, **kwargs)

        # تحديث التقييم الأصلي ليعكس آخر معايرة
        ev = self.evaluation
        ev.calibrated_score_pct = self.new_score_pct
        ev.calibration_reason = self.reason
        ev.calibration_applied_at = timezone.now()
        ev.calibration_applied_by = self.applied_by
        ev.save(
            update_fields=[
                "calibrated_score_pct",
                "calibration_reason",
                "calibration_applied_at",
                "calibration_applied_by",
                "updated_at",
                "updated_by",
            ]
        )


class DailyRatingFactor(CompanyOwnedMixin, ActivableMixin, TimeStampedMixin, UserStampedMixin, models.Model):
    """
    عنصر تقييمي يومي (سلوك – التزام – تعاون – جودة – ..إلخ)
    قابل للإنشاء من الـ Admin بدون تعديل الكود.
    """

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    # الوزن يسمح بتجميع نقاط هذه العوامل بشكل مختلف (اختياري)
    weight_pct = models.PositiveIntegerField(default=100, help_text="Weight inside daily rating aggregation (0..100).")

    class Meta:
        db_table = "perf_daily_rating_factor"
        ordering = ["company", "name"]
        unique_together = [("company", "name")]
        indexes = [
            models.Index(fields=["company", "active"]),
            models.Index(fields=["company", "name"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.weight_pct}%)"


class DailyRating(CompanyOwnedMixin, TimeStampedMixin, UserStampedMixin, models.Model):
    """
    تقييم يومي لموظّف واحد، يحتوي على عدة عناصر RatingItems.
    """
    employee = models.ForeignKey("hr.Employee", on_delete=models.CASCADE, related_name="daily_ratings")
    rated_by = models.ForeignKey(
        "hr.Employee",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="given_daily_ratings",
        help_text="Usually the direct manager.",
    )

    date = models.DateField(db_index=True)
    overall_score_pct = models.PositiveIntegerField(default=0, help_text="Aggregated score of rating items (0..100).")

    class Meta:
        db_table = "perf_daily_rating"
        unique_together = [("employee", "date")]
        ordering = ["-date", "employee"]
        indexes = [models.Index(fields=["employee", "date"])]

    def __str__(self):
        return f"{self.employee.name} – {self.date}: {self.overall_score_pct}%"

    def recompute(self):
        """
        تجميع نتائج RatingItems مع الأوزان.
        """
        items = self.items.select_related("factor").all()
        if not items:
            self.overall_score_pct = 0
            return

        total_weight = sum(i.factor.weight_pct for i in items) or 1
        weighted = sum(i.score_pct * i.factor.weight_pct for i in items)

        self.overall_score_pct = min(100, max(0, int(round(weighted / total_weight))))


class DailyRatingItem(TimeStampedMixin, UserStampedMixin, models.Model):
    """
    نتيجة تقييم عنصر واحد (Factor) ضمن تقييم يومي واحد.
    """

    daily_rating = models.ForeignKey(
        "performance.DailyRating",
        on_delete=models.CASCADE,
        related_name="items"
    )

    factor = models.ForeignKey(
        "performance.DailyRatingFactor",
        on_delete=models.CASCADE,
        related_name="rating_items"
    )

    score_pct = models.PositiveIntegerField(default=0, help_text="0..100")
    comment = models.TextField(blank=True)

    class Meta:
        db_table = "perf_daily_rating_item"
        unique_together = [("daily_rating", "factor")]
        indexes = [
            models.Index(fields=["daily_rating", "factor"]),
            models.Index(fields=["score_pct"]),
        ]

    def __str__(self):
        return f"{self.factor.name}: {self.score_pct}%"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # كلما قمنا بحفظ عنصر، نعيد حساب التقييم اليومي
        self.daily_rating.recompute()
        self.daily_rating.save(update_fields=["overall_score_pct"])


# ---------------------------------------------------------------------------------
# PerformanceExceptionType , PerformanceException  , EvaluationExceptionAdjustment
# --------------------------------------------------------------------------------

class PerformanceExceptionType(CompanyOwnedMixin, ActivableMixin, TimeStampedMixin, UserStampedMixin, models.Model):
    """
    Defines the type/category of performance exceptions.
    Examples: Internet Down, Sick Leave, System Outage, Force Majeure.
    """

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    # كيف يؤثر هذا النوع على التقييم؟
    # مثال: المرض لا يجب أن يخفض التقييم → multiplier = 0
    # مثال: انقطاع الانترنت يقلل عبء العمل → multiplier = +10%
    # multiplier مثال: 0 = no effect ، 0.1 = +10% ، -0.1 = -10%
    multiplier = models.FloatField(
        default=0.0,
        help_text="Impact multiplier applied to final score or specific parameters."
    )

    # هل الاستثناء يساعد الموظف (يخفف عليه)، أم ضده
    is_positive = models.BooleanField(
        default=True,
        help_text="True = beneficial to employee (reduces penalty), False = negative."
    )

    # يمكن تحديد الحد الأقصى لتأثيره
    max_impact_pct = models.PositiveIntegerField(
        default=100,
        help_text="Maximum allowed impact from this exception type."
    )

    class Meta:
        db_table = "perf_exception_type"
        ordering = ["company", "name"]
        unique_together = [("company", "name")]

    def __str__(self):
        return f"{self.name} (multiplier={self.multiplier})"


class PerformanceException(CompanyOwnedMixin, TimeStampedMixin, UserStampedMixin, models.Model):
    """
    Actual exception applied to an employee over a date range.
    """

    employee = models.ForeignKey("hr.Employee", on_delete=models.CASCADE, related_name="performance_exceptions")
    type = models.ForeignKey("performance.PerformanceExceptionType", on_delete=models.CASCADE, related_name="exceptions")

    date_start = models.DateField()
    date_end = models.DateField()

    impact_pct = models.FloatField(
        default=0.0,
        help_text="Optional explicit impact override. If set, overrides type.multiplier."
    )

    notes = models.TextField(blank=True)

    class Meta:
        db_table = "perf_exception"
        ordering = ["-date_start"]
        indexes = [
            models.Index(fields=["employee", "date_start"]),
            models.Index(fields=["type"]),
        ]

    def __str__(self):
        return f"{self.employee.name} — {self.type.name} ({self.date_start} to {self.date_end})"


class EvaluationExceptionAdjustment(TimeStampedMixin, UserStampedMixin, models.Model):
    """
    Stores final adjustment applied to an evaluation due to exceptions.
    """

    evaluation = models.ForeignKey("performance.Evaluation", on_delete=models.CASCADE,
                                   related_name="exception_adjustments")

    exception = models.ForeignKey("performance.PerformanceException", on_delete=models.CASCADE,
                                  related_name="evaluation_adjustments")

    # النتيجة النهائية للـ adjustment بعد الحساب
    adjustment_pct = models.FloatField(
        default=0.0,
        help_text="Final adjustment added to evaluation final score (can be negative or positive)."
    )

    class Meta:
        db_table = "perf_evaluation_exception_adjustment"
        ordering = ["-id"]

    def __str__(self):
        return f"Eval #{self.evaluation.id} Exception Adjust: {self.adjustment_pct:+.2f}%"
