from django.db import models
from base.models.mixins import TimeStampedMixin, UserStampedMixin

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
