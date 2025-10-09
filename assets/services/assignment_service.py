# assets/services/assignment_service.py
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from assets.models import EmployeeAsset, AssetItem

class AssignmentService:

    @staticmethod
    @transaction.atomic
    def assign_item(item: AssetItem, employee, date_assigned=None, due_back=None, note=""):
        if item.status in {"lost", "scrapped"}:
            raise ValidationError("Cannot assign lost or scrapped items.")
        if EmployeeAsset.objects.filter(item=item, is_active=True).exists():
            raise ValidationError("This item is already assigned.")
        rec = EmployeeAsset.objects.create(
            employee=employee,
            item=item,
            date_assigned=date_assigned or timezone.now().date(),
            due_back=due_back,
            handover_note=note,
        )
        return rec

    @staticmethod
    @transaction.atomic
    def return_item(assignment: EmployeeAsset, date_returned=None, note=""):
        if not assignment.is_active:
            return assignment
        assignment.mark_returned(date_returned=date_returned, return_note=note)
        return assignment

    @staticmethod
    @transaction.atomic
    def transfer_item(item: AssetItem, to_employee, date_assigned=None, due_back=None, note=""):
        # إرجاع التسليم الحالي ثم إنشاء تسليم جديد
        curr = EmployeeAsset.objects.filter(item=item, is_active=True).first()
        if curr:
            AssignmentService.return_item(curr, date_returned=date_assigned or timezone.now().date(), note="Auto-transfer")
        return AssignmentService.assign_item(item, to_employee, date_assigned=date_assigned, due_back=due_back, note=note)
