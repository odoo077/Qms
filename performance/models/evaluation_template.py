from django.db import models
from base.models.mixins import TimeStampedMixin, UserStampedMixin, ActivableMixin

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
