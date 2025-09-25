from django.db import models

class ObjectiveDepartmentAssignment(models.Model):
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

    def __str__(self):
        return f"{self.objective.title} → {self.department.complete_name} ({'with' if self.include_children else 'no'} children)"
