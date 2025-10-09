from django.db import models
from base.models.mixins import TimeStampedMixin, UserStampedMixin

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
