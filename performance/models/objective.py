from django.db import models, transaction
from django.core.exceptions import ValidationError
from .mixins import TimeStamped


class Objective(TimeStamped):
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
        from .task import Task
        from .kpi import KPI
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
        from .objective_participant import ObjectiveParticipant
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
