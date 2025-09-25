from django.db import models
from .mixins import TimeStamped

class EvaluationParameter(TimeStamped):
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
        unique_together = [("template", "code")]

    def __str__(self):
        return f"{self.template.name}: {self.name} ({self.weight_pct}%)"
