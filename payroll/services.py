# -*- coding: utf-8 -*-
"""
Services — توليد القسائم للفترة/الموظف مع مراعاة الراتب الأساسي + البنود المتكررة + التسويات.
"""

from decimal import Decimal
from django.db import transaction

# ✅ مهم: استيراد الموديلات لمنع Unresolved reference
from .models import (
    EmployeeSalary, RecurringComponent, MonthlyAdjustment,
    Payslip, PayslipLine, PayrollPeriod
)


def _overlaps(start, end, period_from, period_to):
    """True if [start,end] intersects [period_from,period_to]; None=end = open."""
    end = end or period_to
    return start <= period_to and end >= period_from


def _current_salary(employee, period: PayrollPeriod):
    """الراتب الذي يتقاطع مع فترة الرواتب؛ نفضّل أحدث date_start."""
    qs = (EmployeeSalary._base_manager  # غير مقيّد
          .filter(employee=employee, company_id=period.company_id, date_start__lte=period.date_to)
          .order_by("-date_start"))
    for row in qs:
        if _overlaps(row.date_start, row.date_end, period.date_from, period.date_to):
            return row
    return None


def _active_recurring(employee, period: PayrollPeriod):
    """بنود متكررة فعّالة ومتقاطعة مع الفترة."""
    rows = (RecurringComponent._base_manager  # غير مقيّد
            .filter(employee=employee, company_id=period.company_id, active=True,
                    date_start__lte=period.date_to)
            .order_by("kind", "name"))
    return [r for r in rows if _overlaps(r.date_start, r.date_end, period.date_from, period.date_to)]


def _monthly_adjustments(employee, period: PayrollPeriod):
    """تسويات الشهر لهذه الفترة."""
    return (MonthlyAdjustment._base_manager  # غير مقيّد
            .filter(employee=employee, company_id=period.company_id, period=period)
            .order_by("kind", "name"))

@transaction.atomic
def generate_payslip(employee, period: PayrollPeriod, *, overwrite: bool = False, note: str = "") -> Payslip:
    """
    ابْنِ (أو أعد بناء) قسيمة موظف لفترة معيّنة.
    - overwrite=True: يحذف السطور القديمة ويعيد بناءها إذا كانت القسيمة موجودة.
    """
    slip, created = Payslip.objects.get_or_create(
        employee=employee,
        period=period,
        defaults={"company": period.company, "note": note},
    )
    if not created:
        if overwrite:
            slip.lines.all().delete()
        else:
            # موجودة وممنوع الكتابة فوقها
            return slip

    # snapshot header (company/department/job)
    slip.company = period.company
    slip.department = slip.department or employee.department
    slip.job = slip.job or employee.job
    slip.save(update_fields=["company", "department", "job"])

    # BASIC
    sal = _current_salary(employee, period)
    if sal:
        PayslipLine.objects.create(payslip=slip, name="Basic Salary", kind="basic", amount=sal.amount)

    # RECURRING
    for comp in _active_recurring(employee, period):
        PayslipLine.objects.create(
            payslip=slip, name=comp.name,
            kind=("allowance" if comp.kind == "allowance" else "deduction"),
            amount=comp.amount,
        )

    # ONE-OFFS
    for adj in _monthly_adjustments(employee, period):
        PayslipLine.objects.create(
            payslip=slip, name=adj.name,
            kind=("allowance" if adj.kind == "allowance" else "deduction"),
            amount=adj.amount,
        )

    # recompute totals
    slip.recompute(persist=True)
    return slip


@transaction.atomic
def generate_payslips_for_period(period: PayrollPeriod, employees_qs, *, overwrite: bool = False) -> list[Payslip]:
    """
    توليد قسائم لمجموعة موظفين في فترة واحدة (مع احترام الشركة).
    """
    slips: list[Payslip] = []
    for emp in employees_qs.select_related("company", "department", "job"):
        if emp.company_id != period.company_id:
            continue
        slips.append(generate_payslip(emp, period, overwrite=overwrite))
    return slips
