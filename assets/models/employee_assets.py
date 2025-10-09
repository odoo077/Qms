# assets/models/employee_assets.py
from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from base.models.mixins import CompanyOwnedMixin, TimeStampedMixin, UserStampedMixin
from .assets_item import AssetItem

class EmployeeAsset(CompanyOwnedMixin, TimeStampedMixin, UserStampedMixin):
    """
    Assignment record (history). Exactly one active assignment per item.
    Denormalized company = item.company (يحسّن الفلترة/الفهارس).
    """
    employee = models.ForeignKey("hr.Employee", on_delete=models.CASCADE,
                                 related_name="asset_assignments", db_index=True)
    item = models.ForeignKey(AssetItem, on_delete=models.CASCADE,
                             related_name="assignments", db_index=True)

    date_assigned = models.DateField()
    due_back = models.DateField(null=True, blank=True)
    date_returned = models.DateField(null=True, blank=True)

    # stored compute flags
    is_active = models.BooleanField(default=True, db_index=True)   # active = not returned yet
    is_overdue = models.BooleanField(default=False, db_index=True) # due_back passed and not returned

    handover_note = models.TextField(blank=True)
    return_note = models.TextField(blank=True)

    # CompanyOwnedMixin يضيف company؛ سنملؤه تلقائيًا من item.company في clean/save
    company_dependent_relations = ("employee", "item")

    class Meta:
        db_table = "emp_asset_assignment"
        ordering = ["-date_assigned"]
        constraints = [
            models.UniqueConstraint(
                fields=["item"],
                condition=models.Q(is_active=True),
                name="uniq_active_assignment_per_item",
            ),
        ]
        indexes = [
            models.Index(fields=["company", "is_active"]),
            models.Index(fields=["company", "employee", "is_active"]),
        ]

    def __str__(self):
        return f"{self.item.asset_tag} → {getattr(self.employee, 'name', self.employee_id)}"

    def _compute_flags(self):
        self.is_active = self.date_returned is None
        today = timezone.now().date()
        self.is_overdue = bool(self.is_active and self.due_back and self.due_back < today)

    def clean(self):
        super().clean()
        # الشركة = شركة العنصر (denorm)
        if self.item_id and self.item.company_id:
            self.company_id = self.item.company_id
        # تحقق اتساق الشركة بين الموظف والعنصر
        if self.item and self.employee and self.item.company_id != self.employee.company_id:
            raise ValidationError({"item": "Item company must match employee company."})

    @transaction.atomic
    def save(self, *args, **kwargs):
        self._compute_flags()
        # denorm الشركة قبل الحفظ
        if self.item_id and self.item.company_id:
            self.company_id = self.item.company_id
        super().save(*args, **kwargs)

        # تحديث حالة وكاش الحامل على الـ Item
        item = self.item.__class__.objects.select_for_update().get(pk=self.item_id)
        if self.is_active:
            item.current_employee_id = self.employee_id
            item.status = "assigned"
        else:
            # ابحث عن آخر تسليم نشط (غير هذا السجل) إن وجد
            other_active = self.__class__.objects.filter(item=item, is_active=True).exclude(pk=self.pk)\
                               .order_by("-date_assigned").values_list("employee_id", flat=True).first()
            item.current_employee_id = other_active or None
            if not other_active:
                # لا سجلات نشطة: ارجعه للمخزون إن لم يكن مفقود/معطوب
                if item.status == "assigned":
                    item.status = "in_stock"
        item.save(update_fields=["current_employee", "status"])

    def mark_returned(self, date_returned=None, return_note=""):
        self.date_returned = date_returned or timezone.now().date()
        if return_note:
            self.return_note = return_note
        self.save()
