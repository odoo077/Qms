from django.db import models
from django.core.exceptions import ValidationError
from base.models.mixins import TimeStampedMixin, UserStampedMixin, ActivableMixin

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
