from django.db import models, transaction
from django.core.exceptions import ValidationError
from .mixins import TimeStamped
from .assets_item import AssetItem


class EmployeeAsset(TimeStamped):
    """
    Assignment record (history). One active assignment per item.
    """
    employee = models.ForeignKey("hr.Employee", on_delete=models.CASCADE, related_name="asset_assignments", db_index=True)
    item = models.ForeignKey(AssetItem, on_delete=models.CASCADE, related_name="assignments", db_index=True)

    date_assigned = models.DateField()
    due_back = models.DateField(null=True, blank=True)
    date_returned = models.DateField(null=True, blank=True)

    # stored compute flags (fast filters, Odoo-like store=True)
    is_active = models.BooleanField(default=True, db_index=True)   # active = not returned yet
    is_overdue = models.BooleanField(default=False, db_index=True) # due_back passed and not returned

    handover_note = models.TextField(blank=True)
    return_note = models.TextField(blank=True)

    class Meta:
        db_table = "emp_asset_assignment"
        ordering = ["-date_assigned"]
        constraints = [
            # one active assignment per item
            models.UniqueConstraint(
                fields=["item"],
                condition=models.Q(is_active=True),
                name="uniq_active_assignment_per_item",
            ),
        ]

    def __str__(self):
        return f"{self.item.asset_tag} → {self.employee.name}"

    def _compute_flags(self):
        self.is_active = self.date_returned is None
        self.is_overdue = bool(self.is_active and self.due_back and self.due_back < models.functions.Now().func.now().date())

    def clean(self):
        super().clean()
        # company consistency
        if self.item and self.employee and self.item.company_id != self.employee.company_id:
            raise ValidationError({"item": "Item company must match employee company."})

    @transaction.atomic
    def save(self, *args, **kwargs):
        # stored computes before save
        self._compute_flags()
        super().save(*args, **kwargs)

        # maintain item cache & status after save
        item = self.item
        if self.is_active:
            item.current_employee_id = self.employee_id
            item.status = "assigned"
        else:
            # if no other active assignment, clear holder and put in stock
            has_other = EmployeeAsset.objects.filter(item=item, is_active=True).exclude(pk=self.pk).exists()
            item.current_employee_id = self.employee_id if has_other else None
            if not has_other and item.status == "assigned":
                item.status = "in_stock"
        item.save(update_fields=["current_employee", "status"])

    def mark_returned(self, date_returned=None, return_note=""):
        self.date_returned = date_returned or models.functions.Now()
        if return_note:
            self.return_note = return_note
        self.save()
