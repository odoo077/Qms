from django.db import models, transaction
from django.core.exceptions import ValidationError
from .mixins import TimeStamped
from performance.services.scoring import clamp_to_pct, objective_applies, avg_task_progress_for
from performance.services.metrics import get_adapter


class Evaluation(TimeStamped):
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

    class Meta:
        db_table = "perf_evaluation"
        indexes = [
            models.Index(fields=["company", "employee", "date_start", "date_end"]),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(date_start__lte=models.F("date_end")), name="chk_eval_dates"),
            models.UniqueConstraint(fields=["employee", "date_start", "date_end"], name="uniq_eval_employee_period"),
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
        from .evaluation_parameter_result import EvaluationParameterResult
        from .evaluation_parameter import EvaluationParameter as EP

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
        super().save(*args, **kwargs)
        self.recompute()
        super().save(update_fields=["final_score_pct"])
