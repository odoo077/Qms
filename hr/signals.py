# hr/signals.py
# ============================================================
# HR Signals — Odoo-like Behavior
#
# Responsibilities:
# - Ensure work_contact per Employee (company-scoped)
# - Maintain Partner.employee flag consistency
# - Apply / revoke object-level ACLs on Employee changes
# - Maintain Job counters (no_of_employee / expected_employees)
#
# IMPORTANT:
# - Business logic is intentionally kept here (Odoo-like)
# - dispatch_uid is mandatory for production safety

# NOTE:
# Signals in this module intentionally use transaction.on_commit()
# instead of wrapping logic in atomic().
# This ensures all side effects (ACL, counters, partner flags)
# are applied only after the main DB transaction is fully committed.

# ============================================================

from __future__ import annotations

from django.apps import apps
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models.signals import post_migrate, pre_save, post_save, post_delete
from django.dispatch import receiver


# ============================================================
# Helpers
# ============================================================

def _get_model(app_label: str, model_name: str):
    return apps.get_model(app_label, model_name)


def _company_partner_for(company_id):
    Partner = _get_model("base", "Partner")
    return Partner.objects.filter(company_id=company_id, is_company=True).first()


def _flag_partner_employee(partner_id, value: bool):
    if not partner_id:
        return
    Partner = _get_model("base", "Partner")
    Partner.objects.filter(pk=partner_id).update(employee=value)


# ============================================================
# 1) Ensure Employee.work_contact (Odoo-like)
# ============================================================

@receiver(
    post_save,
    sender=_get_model("hr", "Employee"),
    dispatch_uid="hr.ensure_employee_work_contact.v3",
)
def ensure_employee_work_contact(sender, instance, created: bool, **kwargs):
    """
    Idempotent logic:
    - If linked to user → always use user.partner
    - Otherwise reuse or create a Partner inside the company
    - Maintain Partner.employee flag integrity
    """
    Partner = _get_model("base", "Partner")
    Emp = sender

    # Prevent re-entry in same request
    if getattr(instance, "_work_contact_ensured", False):
        return
    setattr(instance, "_work_contact_ensured", True)

    # Current DB value
    db_wc_id = None
    if instance.pk:
        db_wc_id = (
            Emp.objects
            .filter(pk=instance.pk)
            .values_list("work_contact_id", flat=True)
            .first()
        )

    user = getattr(instance, "user", None)
    up_id = getattr(user, "partner_id", None)

    def _use_partner(pid: int):
        old_id = db_wc_id
        if old_id != pid:
            Emp.objects.filter(pk=instance.pk).update(work_contact_id=pid)
            instance.work_contact_id = pid
            if old_id and old_id != pid and not Emp.objects.filter(work_contact_id=old_id).exists():
                Partner.objects.filter(pk=old_id, employee=True).update(employee=False)
        Partner.objects.filter(pk=pid, employee=False).update(employee=True)

    # Case 1: User-linked employee
    if up_id:
        updates = {}
        if (
            instance.company_id
            and Partner.objects.filter(pk=up_id)
            .exclude(company_id=instance.company_id)
            .exists()
        ):
            updates["company_id"] = instance.company_id
            company_partner = _company_partner_for(instance.company_id)
            updates["parent_id"] = getattr(company_partner, "id", None)

        if updates:
            Partner.objects.filter(pk=up_id).update(**updates)

        _use_partner(up_id)
        return

    # Case 2: work_contact already set
    if getattr(instance, "work_contact_id", None):
        _flag_partner_employee(instance.work_contact_id, True)
        return

    # Case 3: already stored in DB
    if db_wc_id:
        Partner.objects.filter(pk=db_wc_id, employee=False).update(employee=True)
        return

    # Case 4: do not create on update
    if not created:
        return

    # Case 5: reuse or create
    from django.db.models import Q
    company_partner = _company_partner_for(instance.company_id)
    parent_id = getattr(company_partner, "id", None)

    reuse = (
        Partner.objects
        .filter(company_id=instance.company_id, is_company=False)
        .filter(Q(type="contact") | Q(type__isnull=True))
        .filter(Q(name=instance.name) | Q(display_name=instance.name))
        .order_by("id")
        .first()
    )

    partner = reuse or Partner.objects.create(
        company_id=instance.company_id,
        is_company=False,
        name=instance.name,
        parent_id=parent_id,
        employee=True,
        type="contact",
        display_name=instance.name,
    )

    updates = {
        "is_company": False,
        "company_type": "person",
        "type": "contact",
        "company_id": instance.company_id,
        "parent_id": parent_id,
        "employee": True,
    }
    updates = {k: v for k, v in updates.items() if v is not None}

    if not getattr(partner, "display_name", None):
        updates["display_name"] = instance.name

    if updates:
        Partner.objects.filter(pk=partner.id).update(**updates)

    _use_partner(partner.id)


# ============================================================
# 3) Capture Old Values (pre_save)
# ============================================================

@receiver(
    pre_save,
    sender=_get_model("hr", "Employee"),
    dispatch_uid="hr.employee.capture_old_values",
)
def _employee_capture_old_vals(sender, instance, **kwargs):
    if instance.pk:
        try:
            old = sender.objects.only(
                "job_id", "active", "user_id",
                "work_contact_id", "department_id"
            ).get(pk=instance.pk)
            instance._old_job_id = old.job_id
            instance._old_active = old.active
            instance._old_user_id = old.user_id
            instance._old_work_contact_id = old.work_contact_id
            instance._old_department_id = old.department_id
        except sender.DoesNotExist:
            instance._old_job_id = None
            instance._old_active = None
            instance._old_user_id = None
            instance._old_work_contact_id = None
            instance._old_department_id = None
    else:
        instance._old_job_id = None
        instance._old_active = None
        instance._old_user_id = None
        instance._old_work_contact_id = None
        instance._old_department_id = None

# ============================================================
# 4) Job Counters (Employee ↔ Job)
# ============================================================

def recompute_job_counters(job_id):
    if not job_id:
        return
    Employee = _get_model("hr", "Employee")
    Job = _get_model("hr", "Job")
    try:
        job = Job.objects.get(pk=job_id)
    except Job.DoesNotExist:
        return

    count = Employee.objects.filter(job_id=job_id, active=True).count()
    expected = count + (job.no_of_recruitment or 0)

    Job.objects.filter(pk=job_id).update(
        no_of_employee=count,
        expected_employees=expected,
    )


@receiver(
    post_save,
    sender=_get_model("hr", "Employee"),
    dispatch_uid="hr.employee.recompute_job_after_save",
)
def _employee_recompute_jobs_after_save(sender, instance, created, **kwargs):
    new_job_id = instance.job_id
    old_job_id = getattr(instance, "_old_job_id", None)
    old_active = getattr(instance, "_old_active", None)

    def _on_commit():
        if created:
            recompute_job_counters(new_job_id)
        else:
            changed_job = old_job_id != new_job_id
            changed_active = old_active is not None and old_active != instance.active
            if changed_job or changed_active:
                if old_job_id and old_job_id != new_job_id:
                    recompute_job_counters(old_job_id)
                recompute_job_counters(new_job_id)

    transaction.on_commit(_on_commit)


@receiver(
    post_delete,
    sender=_get_model("hr", "Employee"),
    dispatch_uid="hr.employee.recompute_job_after_delete",
)
def _employee_recompute_jobs_after_delete(sender, instance, **kwargs):
    transaction.on_commit(lambda: recompute_job_counters(instance.job_id))


@receiver(
    post_save,
    sender=_get_model("hr", "Job"),
    dispatch_uid="hr.job.recompute_expected_on_recruitment",
)
def _job_recompute_expected_on_recruitment(sender, instance, **kwargs):
    def _on_commit():
        expected = (instance.no_of_employee or 0) + (instance.no_of_recruitment or 0)
        sender.objects.filter(pk=instance.pk).update(expected_employees=expected)
    transaction.on_commit(_on_commit)


# ============================================================
# 5) Partner.employee cleanup on Employee delete
# ============================================================

@receiver(
    post_delete,
    sender=_get_model("hr", "Employee"),
    dispatch_uid="hr.employee.unflag_partner_on_delete",
)
def _employee_unflag_partner_on_delete(sender, instance, **kwargs):
    if not instance.work_contact_id:
        return
    Emp = sender
    Partner = _get_model("base", "Partner")
    if not Emp.objects.filter(work_contact_id=instance.work_contact_id).exists():
        Partner.objects.filter(pk=instance.work_contact_id, employee=True).update(employee=False)


# ============================================================
# Employee Status bootstrap (post_migrate)
# ============================================================

@receiver(post_migrate, dispatch_uid="hr.bootstrap_employee_statuses.v1")
def bootstrap_employee_statuses(sender, **kwargs):
    """
    Create default Employee Statuses (idempotent).

    This runs after migrations and ensures that the system
    always has the minimal required statuses.
    """
    try:
        EmployeeStatus = apps.get_model("hr", "EmployeeStatus")
    except LookupError:
        return

    defaults = [
        {
            "name": "Active",
            "code": "active",
            "sequence": 1,
            "is_active_flag": True,
        },
        {
            "name": "Suspended",
            "code": "suspended",
            "sequence": 20,
            "is_active_flag": False,
        },
        {
            "name": "Terminated",
            "code": "terminated",
            "sequence": 30,
            "is_active_flag": False,
        },
    ]

    for vals in defaults:
        EmployeeStatus.objects.get_or_create(
            code=vals["code"],
            defaults=vals,
        )


# ============================================================
# Backfill Employee.current_status for legacy records
# ============================================================

@receiver(post_migrate, dispatch_uid="hr.backfill_employee_current_status.v1")
def backfill_employee_current_status(sender, **kwargs):
    """
    Ensure all existing employees have a current_status.
    Safe to run multiple times.
    """
    Employee = apps.get_model("hr", "Employee")
    EmployeeStatus = apps.get_model("hr", "EmployeeStatus")

    active_status = (
        EmployeeStatus.objects
        .filter(code="active", active=True)
        .first()
    )

    if not active_status:
        return

    qs = Employee.objects.filter(current_status__isnull=True)

    for emp in qs.iterator():
        emp.current_status = active_status
        emp.active = True
        emp.save(update_fields=["current_status", "active"])


# ============================================================
# Employee current_status bootstrap & sync
# ============================================================

@receiver(pre_save, sender=_get_model("hr", "Employee"),
          dispatch_uid="hr.employee.ensure_current_status.v1")
def ensure_employee_current_status(sender, instance, **kwargs):
    """
    Ensure:
    - current_status is always set
    - employee.active follows status.is_active_flag
    """
    # إذا كانت الحالة محددة، اضبط active وفقًا لها
    if instance.current_status_id:
        instance.active = bool(instance.current_status.is_active_flag)
        return

    # إن لم تُحدَّد الحالة (إنشاء/بيانات قديمة): استخدم Active
    EmployeeStatus = _get_model("hr", "EmployeeStatus")
    active_status = (
        EmployeeStatus.objects
        .filter(code="active", active=True)
        .order_by("sequence")
        .first()
    )
    if active_status:
        instance.current_status = active_status
        instance.active = True
