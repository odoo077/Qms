# payroll/services.py
from decimal import Decimal
from django.db import transaction
from django.utils.timezone import now
from payroll.models import (
    PayrollPeriod, EmployeeSalary, RecurringComponent,
    MonthlyAdjustment, Payslip, PayslipLine
)


def _overlaps(start, end, period_from, period_to):
    """True if [start,end] intersects [period_from,period_to], None=end = open."""
    end = end or period_to
    return start <= period_to and end >= period_from


def _current_salary(employee, period):
    """The salary row overlapping period; prefer the most recent start."""
    qs = (EmployeeSalary.objects
          .filter(employee=employee, company=period.company, date_start__lte=period.date_to)
          .order_by("-date_start"))
    for row in qs:
        if _overlaps(row.date_start, row.date_end, period.date_from, period.date_to):
            return row
    return None


def _active_recurring(employee, period):
    """Recurring add/deduct overlapping the period and active."""
    rows = RecurringComponent.objects.filter(
        employee=employee, company=period.company, active=True,
        date_start__lte=period.date_to
    ).order_by("kind", "name")
    return [r for r in rows if _overlaps(r.date_start, r.date_end, period.date_from, period.date_to)]


def _monthly_adjustments(employee, period):
    return MonthlyAdjustment.objects.filter(
        employee=employee, company=period.company, period=period
    ).order_by("kind", "name")


@transaction.atomic
def generate_payslip(employee, period, *, overwrite=False, note=""):
    """
    Build (or rebuild) a payslip snapshot for one employee & period.
    - overwrite: delete existing lines & rebuild if a payslip exists
    """
    slip, created = Payslip.objects.get_or_create(
        employee=employee, period=period, defaults={"company": period.company, "note": note}
    )
    if not created:
        # keep header but wipe lines if overwrite
        if overwrite:
            slip.lines.all().delete()
        else:
            return slip

    # snapshot department/job/company on header (done in model.save(), but ensure set)
    slip.company = period.company
    slip.department = slip.department or employee.department
    slip.job = slip.job or employee.job
    slip.save(update_fields=["company", "department", "job"])

    # BASIC
    sal = _current_salary(employee, period)
    if sal:
        PayslipLine.objects.create(
            payslip=slip, name="Basic Salary", kind="basic", amount=sal.amount
        )

    # RECURRING
    for comp in _active_recurring(employee, period):
        PayslipLine.objects.create(
            payslip=slip, name=comp.name, kind=("allowance" if comp.kind == "allowance" else "deduction"),
            amount=comp.amount
        )

    # ONE-OFFS
    for adj in _monthly_adjustments(employee, period):
        PayslipLine.objects.create(
            payslip=slip, name=adj.name, kind=("allowance" if adj.kind == "allowance" else "deduction"),
            amount=adj.amount
        )

    # recompute totals (also triggered by signals; explicit here for clarity)
    slip.recompute(save=True)
    return slip


@transaction.atomic
def generate_payslips_for_period(period, employees_qs, *, overwrite=False):
    """Generate slips for a set of employees in a period."""
    slips = []
    for emp in employees_qs.select_related("company", "department", "job"):
        if emp.company_id != period.company_id:
            continue
        slips.append(generate_payslip(emp, period, overwrite=overwrite))
    return slips
