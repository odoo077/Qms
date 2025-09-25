from django.db import models
from django.core.exceptions import ValidationError
from .mixins import TimeStamped

class Task(TimeStamped):
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
