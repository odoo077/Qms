# -*- coding: utf-8 -*-
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
    ActivableMixin,     # active
    TimeStampedMixin,   # created_at / updated_at
    UserStampedMixin,   # created_by / updated_by
)

# خدمات مساعدة (Adapters + Utilities)
from performance.services import (
    get_adapter,
    clamp_to_pct,
    objective_applies,
    avg_task_progress_for,
)


# ------------------------------------------------------------
# Task
# ------------------------------------------------------------
class Task(TimeStampedMixin, UserStampedMixin, ActivableMixin):
    """
    مهام تنفيذية تحت Objective (قد ترتبط بـ KPI).
    """
    STATUS = [
        ("todo", "To Do"),
        ("in_progress", "In Progress"),
        ("blocked", "Blocked"),
        ("done", "Done"),
        ("cancelled", "Cancelled"),
    ]

    company   = models.ForeignKey("base.Company", on_delete=models.PROTECT, related_name="perf_tasks")
    objective = models.ForeignKey("performance.Objective", on_delete=models.CASCADE, related_name="tasks")
    kpi       = models.ForeignKey("performance.KPI", null=True, blank=True, on_delete=models.SET_NULL, related_name="tasks")

    title       = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    assignee = models.ForeignKey("hr.Employee", null=True, blank=True, on_delete=models.SET_NULL, related_name="performance_tasks")
    due_date = models.DateField(null=True, blank=True)
    status   = models.CharField(max_length=12, choices=STATUS, default="todo", db_index=True)

    # 0..100; تُستخدم لتجميع تقدّم الـ Objective
    percent_complete = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "perf_task"
        indexes = [
            models.Index(fields=["company", "objective", "status"]),
            models.Index(fields=["due_date"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(percent_complete__gte=0, percent_complete__lte=100),
                name="chk_task_percent_0_100",
            ),
        ]
        permissions = [
            ("assign_task", "Can assign task to employee"),
            ("update_task_progress", "Can update task progress"),
        ]

    def __str__(self):
        return self.title

    def clean(self):
        super().clean()
        if self.objective and self.company and self.objective.company_id != self.company_id:
            raise ValidationError({"objective": "Objective must belong to the same company."})
        if self.kpi and self.kpi.objective_id != self.objective_id:
            raise ValidationError({"kpi": "KPI must belong to the same Objective."})
        if self.assignee and self.assignee.company_id != self.company_id:
            raise ValidationError({"assignee": "Assignee must belong to the same company."})

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # رفع التجميع إلى الـ Objective
        self.objective.recompute_progress_and_score()
        self.objective.save(update_fields=["progress_pct", "score_pct"])


# ------------------------------------------------------------
# KPI
# ------------------------------------------------------------
class KPI(TimeStampedMixin, UserStampedMixin, ActivableMixin):
    """
    مؤشر أداء رئيسي داخل Objective، مع تخزين نتائج attainment/score.
    """
    UNIT_CHOICES = [
        ("#", "Count"),
        ("%", "Percent"),
        ("IQD", "IQD"),
        ("USD", "USD"),
        ("hrs", "Hours"),
        ("custom", "Custom"),
    ]

    company   = models.ForeignKey("base.Company", on_delete=models.PROTECT, related_name="kpis")
    objective = models.ForeignKey("performance.Objective", on_delete=models.CASCADE, related_name="kpis")

    name        = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    unit             = models.CharField(max_length=10, choices=UNIT_CHOICES, default="#")
    higher_is_better = models.BooleanField(default=True, help_text="If False, lower values score higher")

    target_value   = models.DecimalField(max_digits=16, decimal_places=4)
    baseline_value = models.DecimalField(max_digits=16, decimal_places=4, null=True, blank=True)
    current_value  = models.DecimalField(max_digits=16, decimal_places=4, null=True, blank=True)

    # وزن داخل الـ Objective
    weight_pct = models.PositiveIntegerField(default=100)

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
        attainment: مقارنة (current vs target) مع مراعاة اتجاه الأفضلية.
        score: قصّ إلى 0..100.
        """
        if self.current_value is None or self.target_value in (None, 0):
            self.attainment_pct = 0
            self.score_pct = 0
            return

        try:
            cur = float(self.current_value)
            tgt = float(self.target_value)
            if tgt == 0:
                att = 100.0 if cur == 0 else 0.0
            else:
                if self.higher_is_better:
                    att = (cur / tgt) * 100.0
                else:
                    att = (tgt / cur) * 100.0 if cur > 0 else 100.0
        except Exception:
            att = 0.0

        att = max(0.0, min(200.0, att))  # سقف للتمدد
        self.attainment_pct = int(round(min(att, 200.0)))
        self.score_pct      = int(round(max(0.0, min(100.0, att))))

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.recompute()
        super().save(update_fields=["attainment_pct", "score_pct"])
        # رفع التجميع إلى الـ Objective
        self.objective.recompute_progress_and_score()
        self.objective.save(update_fields=["progress_pct", "score_pct"])


# ------------------------------------------------------------
# Objective
# ------------------------------------------------------------
class Objective(CompanyOwnedMixin, TimeStampedMixin, UserStampedMixin, ActivableMixin):
    """
    الهدف: وعاء KPIs/Tasks + تجميع progress/score + مادة للمشاركين.
    """
    STATUS = [
        ("draft", "Draft"),
        ("active", "Active"),
        ("paused", "Paused"),
        ("done", "Done"),
        ("cancelled", "Cancelled"),
    ]

    company  = models.ForeignKey("base.Company", on_delete=models.PROTECT, related_name="objectives")
    reviewer = models.ForeignKey("hr.Employee", null=True, blank=True, on_delete=models.SET_NULL, related_name="reviewed_objectives")

    code        = models.CharField(max_length=32, blank=True)
    title       = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    date_start = models.DateField()
    date_end   = models.DateField(null=True, blank=True)

    status = models.CharField(max_length=12, choices=STATUS, default="draft", db_index=True)

    # وزن داخل مجموع التقييمات
    weight_pct = models.PositiveIntegerField(default=100, help_text="0..100 (%) weight")

    # تجمعات مخزنة
    progress_pct = models.PositiveIntegerField(default=0, help_text="Aggregated from Tasks (0..100)", db_index=True)
    score_pct    = models.PositiveIntegerField(default=0, help_text="Aggregated from KPIs (0..100)")

    class Meta:
        db_table = "perf_objective"
        indexes = [
            models.Index(fields=["company", "status"]),
            models.Index(fields=["date_start", "date_end"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(weight_pct__gte=0, weight_pct__lte=100),
                name="chk_objective_weight_0_100",
            ),
            models.CheckConstraint(
                check=(models.Q(date_end__isnull=True) | models.Q(date_start__lte=models.F("date_end"))),
                name="chk_objective_dates",
            ),
            models.UniqueConstraint(
                fields=["company", "code", "date_start", "date_end"],
                name="uniq_objective_code_company_period",
                condition=~models.Q(code=""),
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

    def clean(self):
        super().clean()
        if self.reviewer and self.reviewer.company_id != self.company_id:
            raise ValidationError({"reviewer": "Reviewer must belong to the same company."})

    # -------- Aggregations --------
    def recompute_progress_and_score(self):
        # Progress من المهام
        tasks = Task.objects.filter(objective=self).exclude(status__in=["cancelled"])
        self.progress_pct = int(round(sum(t.percent_complete for t in tasks) / tasks.count())) if tasks.exists() else 0
        # Score من KPIs (موزون)
        kpis = KPI.objects.filter(objective=self)
        if kpis.exists():
            total_w = sum(k.weight_pct or 0 for k in kpis) or (kpis.count() * 100)
            num = sum((k.score_pct or 0) * (k.weight_pct or 100) for k in kpis)
            self.score_pct = max(0, min(100, int(round(num / total_w))))
        else:
            self.score_pct = 0

    # -------- Participants materialization --------
    def _collect_department_ids(self):
        """
        تجميع الأقسام المستهدفة، مع توسيع الأقسام الأبناء عند الطلب.
        يعتمد على Department.parent_path لسرعة الاختيار.
        """
        from hr.models import Department
        dept_ids = set()
        for a in self.dept_assignments.select_related("department").all():
            if not a.department_id:
                continue
            dept_ids.add(a.department_id)
            if a.include_children:
                parent_path = a.department.parent_path or ""
                if parent_path:
                    q = Department.objects.filter(
                        company_id=self.company_id,
                        parent_path__startswith=parent_path
                    ).values_list("id", flat=True)
                    dept_ids.update(q)
        return dept_ids

    def _collect_employee_ids(self):
        """
        اتحاد الموظفين الصريحين + موظفي الأقسام (مع الأبناء).
        """
        from hr.models import Employee
        emp_ids = set(self.employee_assignments.values_list("employee_id", flat=True))
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

    # -------- Save hook --------
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)  # PK
        self.recompute_progress_and_score()
        super().save(update_fields=["progress_pct", "score_pct"])
        self._rebuild_participants()


# ------------------------------------------------------------
# Objective Assignments & Participants
# ------------------------------------------------------------
class ObjectiveDepartmentAssignment(TimeStampedMixin, UserStampedMixin):
    """إسناد هدف إلى قسم معيّن (مع خيار تضمين الأبناء)."""
    objective       = models.ForeignKey("performance.Objective", on_delete=models.CASCADE, related_name="dept_assignments")
    department      = models.ForeignKey("hr.Department", on_delete=models.CASCADE, related_name="objective_assignments")
    include_children = models.BooleanField(default=True)

    class Meta:
        db_table = "perf_objective_dept_assignment"
        unique_together = [("objective", "department")]
        indexes = [models.Index(fields=["objective", "department"])]
        permissions = [("manage_department_assignments", "Can manage department assignments")]

    def __str__(self):
        return f"{self.objective.title} → {self.department.complete_name} ({'with' if self.include_children else 'no'} children)"


class ObjectiveEmployeeAssignment(TimeStampedMixin, UserStampedMixin):
    """إسناد هدف إلى موظفين محدّدين (إضافة على استهداف الأقسام)."""
    objective = models.ForeignKey("performance.Objective", on_delete=models.CASCADE, related_name="employee_assignments")
    employee  = models.ForeignKey("hr.Employee", on_delete=models.CASCADE, related_name="objective_assignments")

    class Meta:
        db_table = "perf_objective_employee_assignment"
        unique_together = [("objective", "employee")]
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

    class Meta:
        db_table = "perf_objective_participant"
        unique_together = [("objective", "employee")]
        indexes = [models.Index(fields=["employee", "objective"])]
        permissions = [("view_objective_participants", "Can view objective participants")]

    def __str__(self):
        return f"{self.employee.name} ⇢ {self.objective.title}"


# ------------------------------------------------------------
# Evaluation Template / Parameters / Results
# ------------------------------------------------------------
class EvaluationTemplate(TimeStampedMixin, UserStampedMixin, ActivableMixin):
    """
    قالب تقييم رسمي (مثال: Call Center Q1 Form) يُستَخدم لبناء تقييمات لموظفين.
    """
    company = models.ForeignKey("base.Company", on_delete=models.PROTECT, related_name="evaluation_templates")
    name        = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    active      = models.BooleanField(default=True)

    @property
    def total_weight_pct(self) -> int:
        return sum(p.weight_pct or 0 for p in self.parameters.all())

    class Meta:
        db_table = "perf_evaluation_template"
        unique_together = [("company", "name")]
        ordering = ["company", "name"]
        permissions = [
            ("use_evaluation_template", "Can use evaluation template"),
            ("manage_template_parameters", "Can manage template parameters"),
        ]

    def __str__(self):
        return self.name


class EvaluationParameter(TimeStampedMixin, UserStampedMixin):
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

    class Meta:
        db_table = "perf_evaluation_parameter"
        ordering = ["template", "name"]
        constraints = [
            models.CheckConstraint(check=models.Q(weight_pct__gte=0, weight_pct__lte=100), name="chk_param_weight_0_100"),
            models.CheckConstraint(check=models.Q(min_score_pct__gte=0, min_score_pct__lte=100), name="chk_param_min_0_100"),
            models.CheckConstraint(check=models.Q(max_score_pct__gte=0, max_score_pct__lte=100), name="chk_param_max_0_100"),
        ]
        permissions = [("reorder_parameters", "Can reorder evaluation parameters")]
        unique_together = [("template", "code")]

    def __str__(self):
        return f"{self.template.name}: {self.name} ({self.weight_pct}%)"


class EvaluationParameterResult(TimeStampedMixin, UserStampedMixin):
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

    class Meta:
        db_table = "perf_evaluation_parameter_result"
        unique_together = [("evaluation", "parameter")]
        indexes = [models.Index(fields=["evaluation", "parameter"])]
        permissions = [("rate_parameter_result", "Can rate parameter result")]

    def __str__(self):
        return f"{self.evaluation} · {self.parameter.name}: {self.score_pct}%"


# ------------------------------------------------------------
# Evaluation
# ------------------------------------------------------------
class Evaluation(CompanyOwnedMixin, TimeStampedMixin, UserStampedMixin, ActivableMixin):
    """
    تقييم نهاية فترة لموظّف، مرتبط بقالب، ويُنتج نتائج معاملات ودرجة نهائية.
    """
    company   = models.ForeignKey("base.Company", on_delete=models.PROTECT, related_name="evaluations")
    employee  = models.ForeignKey("hr.Employee",  on_delete=models.PROTECT, related_name="evaluations")
    evaluator = models.ForeignKey("hr.Employee",  null=True, blank=True, on_delete=models.SET_NULL, related_name="given_evaluations")

    date_start = models.DateField()
    date_end   = models.DateField()

    template = models.ForeignKey("performance.EvaluationTemplate", null=True, blank=True,
                                 on_delete=models.SET_NULL, related_name="evaluations")

    overall_rating    = models.CharField(max_length=32, blank=True)
    calibration_notes = models.TextField(blank=True)

    final_score_pct = models.PositiveIntegerField(default=0, db_index=True)

    STATE = [
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("calibrated", "Calibrated"),
        ("approved", "Approved"),
        ("locked", "Locked"),
    ]
    state = models.CharField(max_length=12, choices=STATE, default="draft", db_index=True)

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
            models.Index(fields=["state", "date_end"], name="perf_eval_state_idx"),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(date_start__lte=models.F("date_end")), name="chk_eval_dates"),
            models.UniqueConstraint(fields=["employee", "date_start", "date_end"], name="uniq_eval_employee_period"),
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

    def clean(self):
        super().clean()
        if self.employee and self.company and self.employee.company_id != self.company_id:
            raise ValidationError({"employee": "Employee must belong to the same company."})
        if self.template and self.template.company_id != self.company_id:
            raise ValidationError({"template": "Template must belong to the same company."})

    # -------- Scoring Engine --------
    def _external_metric(self, param):
        """
        أولاً نحاول Adapter مسمّى (param.code)، وإلا نرجع إلى generic_model.
        """
        adapter = get_adapter(param.code) if param.code else None
        ctx = {
            "employee_id": self.employee_id,
            "company_id":  self.company_id,
            "date_start":  self.date_start,
            "date_end":    self.date_end,
        }
        if adapter:
            return adapter(context=ctx, param=param)

        generic = get_adapter("generic_model")
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
        return clamp_to_pct(v, lo, hi)

    def _objective_applies_to_employee(self, obj) -> bool:
        return objective_applies(self, obj)

    def _avg_task_progress(self, objective) -> int:
        return avg_task_progress_for(self, objective)

    @transaction.atomic
    def recompute(self):
        """
        احتساب نتائج المعاملات والدرجة النهائية (موزونة).
        لا يُعاد الحساب إذا كان التقييم مقفولًا/معتمدًا.
        """
        if self.is_locked:
            return

        EP = EvaluationParameter
        existing = {r.parameter_id: r for r in self.parameter_results.select_related("parameter")}
        total_weight, weighted_sum = 0, 0

        params = list(self.template.parameters.select_related("objective", "kpi").all()) if self.template_id else []
        for p in params:
            score, raw_number, raw_json = 0, None, None

            if p.source_kind == EP.SourceKind.MANUAL:
                score = p.manual_default_score_pct

            elif p.source_kind == EP.SourceKind.OBJECTIVE_SCORE and p.objective and self._objective_applies_to_employee(p.objective):
                score = p.objective.score_pct

            elif p.source_kind == EP.SourceKind.OBJECTIVE_PROGRESS and p.objective and self._objective_applies_to_employee(p.objective):
                score = p.objective.progress_pct

            elif p.source_kind == EP.SourceKind.KPI_SCORE and p.kpi and self._objective_applies_to_employee(p.kpi.objective):
                score = p.kpi.score_pct

            elif p.source_kind == EP.SourceKind.TASKS_PROGRESS and p.objective and self._objective_applies_to_employee(p.objective):
                score = self._avg_task_progress(p.objective)

            elif p.source_kind == EP.SourceKind.EXTERNAL_METRIC:
                raw_number, raw_json = self._external_metric(p)
                score = raw_number if raw_number is not None else 0

            score = self._clamp(score, p.min_score_pct, p.max_score_pct)

            res = existing.get(p.id)
            if res:
                res.raw_value_number = raw_number
                res.raw_value_json   = raw_json
                res.score_pct        = score
                res.save(update_fields=["raw_value_number", "raw_value_json", "score_pct"])
            else:
                EvaluationParameterResult.objects.create(
                    evaluation=self, parameter=p,
                    raw_value_number=raw_number, raw_value_json=raw_json, score_pct=score
                )

            w = p.weight_pct or 0
            total_weight += w
            weighted_sum += (score * w)

        final = int(round(weighted_sum / total_weight)) if total_weight else 0
        self.final_score_pct = max(0, min(100, final))

    def save(self, *args, **kwargs):
        """
        - حالات مفتوحة: نعيد الحساب ونحفظ الدرجة.
        - حالات معتمدة/مقفولة: لا نعيد الحساب تلقائيًا (سلامة تاريخية).
        """
        super().save(*args, **kwargs)  # لضمان PK
        if self.is_locked:
            return
        self.recompute()
        super().save(update_fields=["final_score_pct"])

    # -------- تحوّلات الحالة --------
    def submit(self, by=None):
        if self.state != "draft":
            return
        self.state = "submitted"
        self.submitted_at = timezone.now()
        if by:
            self.submitted_by = by
        self.recompute()
        super().save(update_fields=["state", "submitted_at", "submitted_by", "final_score_pct"])

    def calibrate(self, by=None):
        if self.state not in ("submitted", "calibrated"):
            return
        self.state = "calibrated"
        self.calibrated_at = timezone.now()
        if by:
            self.calibrated_by = by
        self.recompute()
        super().save(update_fields=["state", "calibrated_at", "calibrated_by", "final_score_pct"])

    def approve(self, by=None):
        if self.state not in ("submitted", "calibrated"):
            return
        self.recompute()
        self.state = "approved"
        self.approved_at = timezone.now()
        if by:
            self.approved_by = by
        super().save(update_fields=["state", "approved_at", "approved_by", "final_score_pct"])

    def lock(self):
        if self.state in ("approved", "locked"):
            self.state = "locked"
            self.locked_at = timezone.now()
            super().save(update_fields=["state", "locked_at"])
