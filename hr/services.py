# hr/services.py
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError

from hr.models import Employee, EmployeeStatus, EmployeeStatusHistory


@transaction.atomic
def change_employee_status(
    *,
    employee: Employee,
    new_status: EmployeeStatus,
    reason: str,
    note: str = "",
    changed_by=None,
):
    """
    The ONLY official way to change employee status.

    Rules:
    - Always creates EmployeeStatusHistory
    - Updates employee.current_status
    - Syncs employee.active with status.is_active_flag
    - Atomic & audit-safe
    """

    if not employee:
        raise ValidationError("Employee is required.")

    if not new_status:
        raise ValidationError("New status is required.")

    if not reason or not reason.strip():
        raise ValidationError("Reason is required to change employee status.")

    # Prevent no-op
    if employee.current_status_id == new_status.id:
        return employee

    # Create history record (append-only)
    EmployeeStatusHistory.objects.create(
        employee=employee,
        status=new_status,
        reason=reason.strip(),
        note=(note or "").strip(),
        changed_by=changed_by,
        changed_at=timezone.now(),
    )

    # Update employee state
    employee.current_status = new_status
    employee.active = bool(new_status.is_active_flag)

    employee.save(
        update_fields=["current_status", "active"],
        _skip_full_clean=True,
    )

    return employee
