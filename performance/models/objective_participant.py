from django.db import models


class ObjectiveParticipant(models.Model):
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

    def __str__(self):
        return f"{self.employee.name} ⇢ {self.objective.title}"
