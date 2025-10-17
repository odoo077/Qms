from django.db import models
from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from base.models import CompanyOwnedMixin, ActivableMixin, TimeStampedMixin, UserStampedMixin
from performance.services import get_adapter, clamp_to_pct, objective_applies, avg_task_progress_for


class Task(TimeStampedMixin, UserStampedMixin, ActivableMixin):
    STATUS = [
        ("todo", "To Do"),
        ("in_progress", "In Progress"),
        ("blocked", "Blocked"),
        ("done", "Done"),
        ("cancelled", "Cancelled"),
    ]
    company = models.ForeignKey("base.Company", on_delete=models.PROTECT, related_name="perf_tasks")
    objective = models.ForeignKey("performance.Objective", on_delete=models.CASCADE, related_name="tasks")
    kpi = models.ForeignKey("performance.KPI", null=True, blank=True, on_delete=models.SET_NULL, related_name="tasks")

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    assignee = models.ForeignKey("hr.Employee", null=True, blank=True, on_delete=models.SET_NULL, related_name="performance_tasks")
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=STATUS, default="todo", db_index=True)

    # 0..100; used by Objective progress stored compute
    percent_complete = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "perf_task"
        indexes = [
            models.Index(fields=["company", "objective", "status"]),
            models.Index(fields=["due_date"]),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(percent_complete__gte=0, percent_complete__lte=100),
                                   name="chk_task_percent_0_100"),
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
        # bubble progress up
        self.objective.recompute_progress_and_score()
        self.objective.save(update_fields=["progress_pct", "score_pct"])
class KPI(TimeStampedMixin, UserStampedMixin, ActivableMixin):
    UNIT_CHOICES = [
        ("#", "Count"),
        ("%", "Percent"),
        ("IQD", "IQD"),
        ("USD", "USD"),
        ("hrs", "Hours"),
        ("custom", "Custom"),
    ]
    company = models.ForeignKey("base.Company", on_delete=models.PROTECT, related_name="kpis")
    objective = models.ForeignKey("performance.Objective", on_delete=models.CASCADE, related_name="kpis")

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    unit = models.CharField(max_length=10, choices=UNIT_CHOICES, default="#")
    higher_is_better = models.BooleanField(default=True, help_text="If False, lower values score higher")

    target_value = models.DecimalField(max_digits=16, decimal_places=4)
    baseline_value = models.DecimalField(max_digits=16, decimal_places=4, null=True, blank=True)
    current_value = models.DecimalField(max_digits=16, decimal_places=4, null=True, blank=True)

    # Weight inside the Objective (0..100)
    weight_pct = models.PositiveIntegerField(default=100)

    # Stored computes
    attainment_pct = models.PositiveIntegerField(default=0, help_text="0..100% of target achieved", db_index=True)
    score_pct = models.PositiveIntegerField(default=0, help_text="0..100 normalized score")

    class Meta:
        db_table = "perf_kpi"
        indexes = [
            models.Index(fields=["company", "objective"]),
            models.Index(fields=["attainment_pct", "score_pct"]),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(weight_pct__gte=0, weight_pct__lte=100), name="chk_kpi_weight_0_100"),
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
        attainment: (current vs target), direction-aware.
        score: clamp to 0..100 from attainment.
        """
        if self.current_value is None or self.target_value in (None, 0):
            self.attainment_pct = 0
            self.score_pct = 0
            return

        # Direction aware attainment
        try:
            cur = float(self.current_value)
            tgt = float(self.target_value)
            if tgt == 0:
                att = 100.0 if cur == 0 else 0.0
            else:
                if self.higher_is_better:
                    att = (cur / tgt) * 100.0
                else:
                    # smaller is better: if cur <= tgt ⇒ at/over 100%
                    att = (tgt / cur) * 100.0 if cur > 0 else 100.0
        except Exception:
            att = 0.0

        att = max(0.0, min(200.0, att))  # cap “stretch” at 200% for sanity
        self.attainment_pct = int(round(min(att, 200.0)))
        # score clamps to 0..100 (policy: >100% counts as 100 score)
        self.score_pct = int(round(max(0.0, min(100.0, att))))

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.recompute()
        super().save(update_fields=["attainment_pct", "score_pct"])

        # Bubble up to objective
        self.objective.recompute_progress_and_score()
        self.objective.save(update_fields=["progress_pct", "score_pct"])
class Objective(CompanyOwnedMixin, TimeStampedMixin, UserStampedMixin, ActivableMixin):
    STATUS = [
        ("draft", "Draft"),
        ("active", "Active"),
        ("paused", "Paused"),
        ("done", "Done"),
        ("cancelled", "Cancelled"),
    ]
    company = models.ForeignKey("base.Company", on_delete=models.PROTECT, related_name="objectives")
    # Optional: a “sponsor / reviewer” for governance (not a participant list)
    reviewer = models.ForeignKey("hr.Employee", null=True, blank=True, on_delete=models.SET_NULL, related_name="reviewed_objectives")

    code = models.CharField(max_length=32, blank=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    date_start = models.DateField()
    date_end = models.DateField(null=True, blank=True)

    status = models.CharField(max_length=12, choices=STATUS, default="draft", db_index=True)

    # Weight controls contribution inside Evaluation aggregates
    weight_pct = models.PositiveIntegerField(default=100, help_text="0..100 (%) weight")

    # Stored computes (progress from Tasks, score from KPIs)
    progress_pct = models.PositiveIntegerField(default=0, help_text="Aggregated from Tasks (0..100)", db_index=True)
    score_pct = models.PositiveIntegerField(default=0, help_text="Aggregated from KPIs (0..100)")

    class Meta:
        db_table = "perf_objective"
        indexes = [
            models.Index(fields=["company", "status"]),
            models.Index(fields=["date_start", "date_end"]),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(weight_pct__gte=0, weight_pct__lte=100), name="chk_objective_weight_0_100"),
            models.CheckConstraint(check=(models.Q(date_end__isnull=True) | models.Q(date_start__lte=models.F("date_end"))),
                                   name="chk_objective_dates"),
            models.UniqueConstraint(fields=["company", "code", "date_start", "date_end"],
                                    name="uniq_objective_code_company_period",
                                    condition=~models.Q(code="")),
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

    # ----------------------------
    # Aggregations (unchanged)
    # ----------------------------
    def recompute_progress_and_score(self):
        # Progress from tasks
        tasks = Task.objects.filter(objective=self).exclude(status__in=["cancelled"])
        self.progress_pct = int(round(sum(t.percent_complete for t in tasks) / tasks.count())) if tasks.exists() else 0
        # Score from KPIs (weighted)
        kpis = KPI.objects.filter(objective=self)
        if kpis.exists():
            total_w = sum(k.weight_pct or 0 for k in kpis) or (kpis.count() * 100)
            num = sum((k.score_pct or 0) * (k.weight_pct or 100) for k in kpis)
            self.score_pct = max(0, min(100, int(round(num / total_w))))
        else:
            self.score_pct = 0

    # ----------------------------
    # Participant materialization
    # ----------------------------
    def _collect_department_ids(self):
        """
        Resolve departments from assignments, expanding children where requested.
        Uses Department.parent_path for fast subtree selection.
        """
        from hr.models import Department
        dept_ids = set()
        for a in self.dept_assignments.select_related("department").all():
            if not a.department_id:
                continue
            # include assigned department
            dept_ids.add(a.department_id)
            if a.include_children:
                # same company & parent_path startswith
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
        Union of explicit employees + employees in (dept + children).
        """
        from hr.models import Employee
        # explicit
        emp_ids = set(self.employee_assignments.values_list("employee_id", flat=True))
        # by departments
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
        target_ids = set(self._collect_employee_ids())

        # Current materialization
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

    # ----------------------------
    # Save hook
    # ----------------------------
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)  # ensure PK
        # recompute aggregates
        self.recompute_progress_and_score()
        super().save(update_fields=["progress_pct", "score_pct"])
        # materialize participants
        self._rebuild_participants()
class ObjectiveDepartmentAssignment(TimeStampedMixin, UserStampedMixin):
    """
    Assign an Objective to a Department. Optionally include all child departments.
    """
    objective = models.ForeignKey("performance.Objective", on_delete=models.CASCADE, related_name="dept_assignments")
    department = models.ForeignKey("hr.Department", on_delete=models.CASCADE, related_name="objective_assignments")
    include_children = models.BooleanField(default=True)

    class Meta:
        db_table = "perf_objective_dept_assignment"
        unique_together = [("objective", "department")]
        indexes = [models.Index(fields=["objective", "department"])]
        permissions = [
            ("manage_department_assignments", "Can manage department assignments"),
        ]

    def __str__(self):
        return f"{self.objective.title} → {self.department.complete_name} ({'with' if self.include_children else 'no'} children)"
class ObjectiveEmployeeAssignment(TimeStampedMixin, UserStampedMixin):
    """
    Assign an Objective to explicit Employees (in addition to department targeting).
    """
    objective = models.ForeignKey("performance.Objective", on_delete=models.CASCADE, related_name="employee_assignments")
    employee = models.ForeignKey("hr.Employee", on_delete=models.CASCADE, related_name="objective_assignments")

    class Meta:
        db_table = "perf_objective_employee_assignment"
        unique_together = [("objective", "employee")]
        indexes = [models.Index(fields=["objective", "employee"])]
        permissions = [
            ("manage_employee_assignments", "Can manage employee assignments"),
        ]

    def __str__(self):
        return f"{self.objective.title} → {self.employee.name}"
class ObjectiveParticipant(TimeStampedMixin):
    """
    Materialized participants (employees) for an Objective.
    This is rebuilt whenever the Objective or its assignments change.
    """
    objective = models.ForeignKey("performance.Objective", on_delete=models.CASCADE, related_name="participants")
    employee = models.ForeignKey("hr.Employee", on_delete=models.CASCADE, related_name="objective_participations")

    class Meta:
        db_table = "perf_objective_participant"
        unique_together = [("objective", "employee")]
        indexes = [models.Index(fields=["employee", "objective"])]
        permissions = [
            ("view_objective_participants", "Can view objective participants"),
        ]

    def __str__(self):
        return f"{self.employee.name} ⇢ {self.objective.title}"

class EvaluationTemplate(TimeStampedMixin, UserStampedMixin, ActivableMixin):
    """
    A formal evaluation form (e.g., 'Call Center Q1 Form').
    Applied to specific employees for a given period.
    """
    company = models.ForeignKey("base.Company", on_delete=models.PROTECT, related_name="evaluation_templates")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)

    # Convenience summary (not enforced at DB)
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
    A row/parameter inside a template.
    Supports different 'sources' (Objective/KPI/Tasks/External/Manual).
    In step 2, Evaluation will read these to compute final scores.
    """
    class SourceKind(models.TextChoices):
        OBJECTIVE_SCORE = "objective_score", "Objective Score (score_pct)"
        OBJECTIVE_PROGRESS = "objective_progress", "Objective Progress (progress_pct)"
        KPI_SCORE = "kpi_score", "KPI Score (score_pct)"
        TASKS_PROGRESS = "tasks_progress", "Tasks Progress (avg % complete)"
        EXTERNAL_METRIC = "external_metric", "External Metric (model/field/filter)"
        MANUAL = "manual", "Manual Entry (default)"

    template = models.ForeignKey("performance.EvaluationTemplate", on_delete=models.CASCADE, related_name="parameters")
    # Shown in the form
    name = models.CharField(max_length=255)               # e.g. "Call handled"
    code = models.CharField(max_length=64, blank=True)    # optional identifier
    weight_pct = models.PositiveIntegerField(help_text="0..100")

    source_kind = models.CharField(max_length=32, choices=SourceKind.choices, default=SourceKind.MANUAL)

    # For Objective/KPI/Tasks
    objective = models.ForeignKey("performance.Objective", null=True, blank=True, on_delete=models.SET_NULL, related_name="eval_params")
    kpi = models.ForeignKey("performance.KPI", null=True, blank=True, on_delete=models.SET_NULL, related_name="eval_params")

    # For EXTERNAL_METRIC: app_label.ModelName, field, aggregation, and optional JSON filter
    external_model = models.CharField(max_length=128, blank=True, help_text="e.g. 'attendance.AttendanceLog'")
    external_field = models.CharField(max_length=64, blank=True, help_text="Field to aggregate (e.g., 'worked_minutes')")
    external_aggregation = models.CharField(max_length=16, blank=True, choices=[("sum","Sum"),("avg","Average"),("latest","Latest")], default="", help_text="How to combine values")
    external_filter = models.JSONField(default=dict, blank=True, help_text="Optional filter JSON (key->value)")

    # For MANUAL fallback/default
    manual_default_score_pct = models.PositiveIntegerField(default=0, help_text="Default 0..100")

    # Optional clamp/map to 0..100 after metric calculation (kept simple; we’ll apply in step 2)
    min_score_pct = models.PositiveIntegerField(default=0)
    max_score_pct = models.PositiveIntegerField(default=100)

    class Meta:
        db_table = "perf_evaluation_parameter"
        ordering = ["template", "name"]
        constraints = [
            models.CheckConstraint(check=models.Q(weight_pct__gte=0, weight_pct__lte=100), name="chk_param_weight_0_100"),
            models.CheckConstraint(check=models.Q(min_score_pct__gte=0, min_score_pct__lte=100), name="chk_param_min_0_100"),
            models.CheckConstraint(check=models.Q(max_score_pct__gte=0, max_score_pct__lte=100), name="chk_param_max_0_100"),
        ]
        permissions = [
            ("reorder_parameters", "Can reorder evaluation parameters"),
        ]
        unique_together = [("template", "code")]

    def __str__(self):
        return f"{self.template.name}: {self.name} ({self.weight_pct}%)"
class EvaluationParameterResult(TimeStampedMixin, UserStampedMixin):
    """
    Stores the computed outcome for a single parameter of a given Evaluation.
    - raw_value: whatever the source produced (number or JSON)
    - score_pct: normalized 0..100 after clamp
    """
    evaluation = models.ForeignKey("performance.Evaluation", on_delete=models.CASCADE, related_name="parameter_results")
    parameter = models.ForeignKey("performance.EvaluationParameter", on_delete=models.CASCADE, related_name="results")

    raw_value_number = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    raw_value_json = models.JSONField(null=True, blank=True)
    score_pct = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "perf_evaluation_parameter_result"
        unique_together = [("evaluation", "parameter")]
        indexes = [models.Index(fields=["evaluation", "parameter"])]
        permissions = [
            ("rate_parameter_result", "Can rate parameter result"),
        ]

    def __str__(self):
        return f"{self.evaluation} · {self.parameter.name}: {self.score_pct}%"
class Evaluation(CompanyOwnedMixin, TimeStampedMixin, UserStampedMixin, ActivableMixin):
    """
    End-of-period evaluation for an employee.
    Now links to a Template and materializes parameter results.
    """
    company = models.ForeignKey("base.Company", on_delete=models.PROTECT, related_name="evaluations")
    employee = models.ForeignKey("hr.Employee", on_delete=models.PROTECT, related_name="evaluations")
    evaluator = models.ForeignKey("hr.Employee", null=True, blank=True, on_delete=models.SET_NULL, related_name="given_evaluations")

    date_start = models.DateField()
    date_end = models.DateField()

    template = models.ForeignKey("performance.EvaluationTemplate", null=True, blank=True,
                                 on_delete=models.SET_NULL, related_name="evaluations")

    overall_rating = models.CharField(max_length=32, blank=True)
    calibration_notes = models.TextField(blank=True)

    final_score_pct = models.PositiveIntegerField(default=0, db_index=True)

    # ======= Workflow / Lifecycle =======
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

    # ----------------------------
    # Scoring Engine
    # ----------------------------

    # def _objective_applies_to_employee(self, obj) -> bool:
    #     """
    #     Only include Objective-bound parameters if this Objective applies to the employee
    #     via materialized participants, and overlaps the evaluation period.
    #     """
    #     from .objective_participant import ObjectiveParticipant
    #     if not obj or obj.company_id != self.company_id:
    #         return False
    #     if obj.date_start > self.date_end:
    #         return False
    #     if obj.date_end and obj.date_end < self.date_start:
    #         return False
    #     return ObjectiveParticipant.objects.filter(objective=obj, employee=self.employee).exists()
    #
    # def _avg_task_progress(self, objective) -> int:
    #     """
    #     Average of Task.percent_complete for the employee (if assignee set) or objective-wide
    #     over the period (due_date intersecting the period). Clamp to 0..100.
    #     """
    #     from .task import Task
    #     qs = Task.objects.filter(objective=objective, company=self.company).exclude(status__in=["cancelled"])
    #     # If you want per-employee daily tasks: prefer assignee filter
    #     qs = qs.filter(models.Q(assignee=self.employee) | models.Q(assignee__isnull=True))
    #     # Period intersection (use due_date if set; otherwise include)
    #     qs = qs.filter(models.Q(due_date__isnull=True) |
    #                    models.Q(due_date__range=(self.date_start, self.date_end)))
    #     count = qs.count()
    #     if not count:
    #         return 0
    #     avg = round(sum(x.percent_complete for x in qs) / count)
    #     return int(max(0, min(100, avg)))
    #
    # def _external_metric(self, param) -> tuple[float | None, dict | None]:
    #     """
    #     Resolve EXTERNAL_METRIC via ContentType-like dynamic import.
    #     We keep it lightweight: app_label.ModelName + simple filter with placeholders.
    #     """
    #     if not (param.external_model and param.external_field and param.external_aggregation):
    #         return None, None
    #     try:
    #         app_label, model_name = param.external_model.split(".", 1)
    #     except ValueError:
    #         return None, None
    #
    #     # Late import to avoid hard deps
    #     from django.apps import apps
    #     Model = apps.get_model(app_label, model_name)
    #     if not Model:
    #         return None, None
    #
    #     q = Model.objects.all()
    #
    #     # Simple placeholder substitution for common keys
    #     # Example external_filter: {"employee_id": "{employee_id}", "date__gte": "{date_start}", "date__lte": "{date_end}"}
    #     flt = {}
    #     for k, v in (param.external_filter or {}).items():
    #         if isinstance(v, str):
    #             v = v.replace("{employee_id}", str(self.employee_id)) \
    #                  .replace("{company_id}", str(self.company_id)) \
    #                  .replace("{date_start}", str(self.date_start)) \
    #                  .replace("{date_end}", str(self.date_end))
    #         flt[k] = v
    #     if flt:
    #         q = q.filter(**flt)
    #
    #     values = q.values_list(param.external_field, flat=True)
    #     vals = [float(x) for x in values if x is not None]
    #
    #     if not vals:
    #         return None, {"count": 0}
    #
    #     if param.external_aggregation == "sum":
    #         raw = sum(vals)
    #     elif param.external_aggregation == "avg":
    #         raw = sum(vals) / len(vals)
    #     elif param.external_aggregation == "latest":
    #         raw = float(values.order_by("-id").first() or 0)  # naive latest by id
    #     else:
    #         raw = None
    #
    #     meta = {"count": len(vals), "agg": param.external_aggregation}
    #     return raw, meta
    #
    # def _clamp(self, v, lo, hi) -> int:
    #     if v is None:
    #         return 0
    #     return int(max(lo, min(hi, round(v))))

    # ----------------------------
    # Scoring Engine
    # ----------------------------

    def _external_metric(self, param):
        """
        Try a named adapter first (param.code), else fall back to generic_model.
        """
        adapter = get_adapter(param.code) if param.code else None
        ctx = {
            "employee_id": self.employee_id,
            "company_id": self.company_id,
            "date_start": self.date_start,
            "date_end": self.date_end,
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
        Compute per-parameter results and the final weighted score.
        """

        # لا تُعيد الحساب إذا كان التقييم مقفولًا أو معتمدًا
        if self.is_locked:
            return

        EP = EvaluationParameter

        # Clear/prepare result map
        existing = { (r.parameter_id): r for r in self.parameter_results.select_related("parameter") }

        total_weight = 0
        weighted_sum = 0

        params = list(self.template.parameters.select_related("objective", "kpi").all()) if self.template_id else []
        for p in params:
            score = 0
            raw_number = None
            raw_json = None

            if p.source_kind == EP.SourceKind.MANUAL:
                score = p.manual_default_score_pct

            elif p.source_kind == EP.SourceKind.OBJECTIVE_SCORE:
                obj = p.objective
                if obj and self._objective_applies_to_employee(obj):
                    score = obj.score_pct

            elif p.source_kind == EP.SourceKind.OBJECTIVE_PROGRESS:
                obj = p.objective
                if obj and self._objective_applies_to_employee(obj):
                    score = obj.progress_pct

            elif p.source_kind == EP.SourceKind.KPI_SCORE:
                kpi = p.kpi
                if kpi and self._objective_applies_to_employee(kpi.objective):
                    score = kpi.score_pct

            elif p.source_kind == EP.SourceKind.TASKS_PROGRESS:
                obj = p.objective
                if obj and self._objective_applies_to_employee(obj):
                    score = self._avg_task_progress(obj)

            elif p.source_kind == EP.SourceKind.EXTERNAL_METRIC:
                raw_number, raw_json = self._external_metric(p)
                # By default assume the external already yields 0..100; clamp handles safety.
                score = raw_number if raw_number is not None else 0

            # Clamp & persist per-parameter result
            score = self._clamp(score, p.min_score_pct, p.max_score_pct)

            # Upsert result row
            res = existing.get(p.id)
            if res:
                res.raw_value_number = raw_number
                res.raw_value_json = raw_json
                res.score_pct = score
                res.save(update_fields=["raw_value_number", "raw_value_json", "score_pct"])
            else:
                EvaluationParameterResult.objects.create(
                    evaluation=self, parameter=p, raw_value_number=raw_number, raw_value_json=raw_json, score_pct=score
                )

            # Weighting
            w = p.weight_pct or 0
            total_weight += w
            weighted_sum += (score * w)

        # Final weighted score (ignore parameters if template missing)
        final = int(round(weighted_sum / total_weight)) if total_weight else 0
        self.final_score_pct = max(0, min(100, final))

    def save(self, *args, **kwargs):
        """
        - في الحالات المفتوحة (draft/submitted/calibrated): احسب وحدث الدرجة النهائية.
        - بعد الموافقة/القفل: لا نعيد الحساب تلقائيًا (سلامة تاريخية).
        - إن أردت إجبار حساب قبل القفل، استدعِ recompute() يدويًا ثم احفظ.
        """
        # حفظ أولي لضمان وجود PK
        super().save(*args, **kwargs)

        # لا نعيد الحساب إذا كان مقفولًا/معتمدًا
        if self.is_locked:
            return

        # إعادة الحساب في الحالات المفتوحة
        self.recompute()
        super().save(update_fields=["final_score_pct"])


    # ======= State Transitions =======
    def submit(self, by:None):
        if self.state != "draft":
            return
        self.state = "submitted"
        self.submitted_at = timezone.now()
        if by:
            self.submitted_by = by
        # مسموح إعادة حساب قبل الاعتماد
        self.recompute()
        super().save(update_fields=["state", "submitted_at", "submitted_by", "final_score_pct"])

    def calibrate(self, by:None):
        if self.state not in ("submitted", "calibrated"):
            return
        self.state = "calibrated"
        self.calibrated_at = timezone.now()
        if by:
            self.calibrated_by = by
        # قد تُعدّل الملاحظات/الأوزان اليدوية ثم يُعاد الحساب
        self.recompute()
        super().save(update_fields=["state", "calibrated_at", "calibrated_by", "final_score_pct"])

    def approve(self, by:None):
        if self.state not in ("submitted", "calibrated"):
            return
        # آخر إعادة حساب قبل القفل
        self.recompute()
        self.state = "approved"
        self.approved_at = timezone.now()
        if by:
            self.approved_by = by
        super().save(update_fields=["state", "approved_at", "approved_by", "final_score_pct"])

    def lock(self):
        # قفل إداري (بعد الموافقة عادةً)
        if self.state in ("approved", "locked"):
            self.state = "locked"
            self.locked_at = timezone.now()
            super().save(update_fields=["state", "locked_at"])
