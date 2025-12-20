# payroll/services.py

from django.db import transaction
from decimal import Decimal, ROUND_HALF_UP
from .models import (
PayrollStructure, SalaryRuleCategory, SalaryRule,
    RuleParameter,
    Payslip, PayslipLine, PayrollPeriod, EmployeeSalary,
)
from django.core.exceptions import ValidationError



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


def _eval_python(expr: str, env: dict[str, object]) -> dict:
    """
    تنفيذ آمن ومحدود: يضبط المتغيرات (result/amount/quantity/rate/total) إن وُجدت.
    """
    # البيئة المسموح بها
    safe_locals = {
        "Decimal": Decimal,
        "min": min, "max": max, "round": round, "abs": abs,
        "inputs": env.get("inputs", {}),
        "result": env.get("result", True),
        "amount": env.get("amount", Decimal("0")),
        "quantity": env.get("quantity", Decimal("1")),
        "rate": env.get("rate", Decimal("100")),
        "total": env.get("total", Decimal("0")),
        "categories": env.get("categories", {}),  # مجاميع سابقة
        "params": env.get("params", {}),  # RuleParameter
        "BASIC": env.get("BASIC", Decimal("0")),  # راتب أساسي
    }
    # لا نفتح builtins ولا globals
    exec(expr, {"__builtins__": {}}, safe_locals)
    return safe_locals


def _collect_inputs(slip: Payslip) -> dict[str, Decimal]:
    """يجمع إدخالات القسيمة حسب الكود (مجموع مبسّط)."""
    agg: dict[str, Decimal] = {}
    for line in slip.inputs.select_related("input_type").all():
        agg[line.code] = agg.get(line.code, Decimal("0.00")) + Decimal(line.amount)
    return agg


def _compute_payslip_by_rules(slip: Payslip):
    """
    يحاكي Odoo: يحمّل القواعد من struct، يختبر الشرط، يحسب (amount/qty/rate/total)،
    يبني PayslipLine ويحدّث مجاميع الفئات + الإجماليات.
    """
    assert slip.struct_id, "Payslip.struct must be set before compute."

    # راتب أساسي صحيح (شركة وتداخل زمني)
    sal = _current_salary(slip.employee, slip.period)
    basic = sal.amount if sal else Decimal("0.00")

    slip.lines.all().delete()

    inputs = _collect_inputs(slip)
    params = {p.code: p.value for p in RuleParameter.objects.filter(company=slip.company)}

    # 2) تحميل القواعد مرتبة
    rules = (SalaryRule.objects
             .filter(struct=slip.struct)
             .select_related("category")
             .order_by("sequence", "id"))

    categories_sum: dict[str, Decimal] = {}  # code -> sum(total)
    gross = Decimal("0.00")
    net = Decimal("0.00")

    # 3) سياق التنفيذ
    ctx_base = {
        "inputs": inputs,
        "params": params,
        "BASIC": basic,
        "categories": categories_sum,
    }

    for rule in rules:
        # شرط
        ok = True
        if rule.condition_select == "python":
            try:
                res = _eval_python(rule.condition_python, ctx_base | {"result": True})
                ok = bool(res.get("result", True))
            except Exception as e:
                raise ValidationError(f"Condition error in rule [{rule.code}]: {e}")
        if not ok:
            continue

        # حساب
        try:
            res = _eval_python(rule.amount_python, ctx_base | {
                "amount": Decimal("0"),
                "quantity": Decimal("1"),
                "rate": Decimal("100"),
                "total": Decimal("0"),
            })
        except Exception as e:
            raise ValidationError(f"Amount error in rule [{rule.code}]: {e}")

        amount = Decimal(str(res.get("amount", 0))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        quantity = Decimal(str(res.get("quantity", 1)))
        rate = Decimal(str(res.get("rate", 100)))
        total = Decimal(str(res.get("total", amount * quantity * rate / Decimal("100")))).quantize(Decimal("0.01"),
                                                                                                   rounding=ROUND_HALF_UP)

        line = PayslipLine.objects.create(
            payslip=slip,
            company=slip.company,
            code=rule.code,
            name=rule.name,
            category=rule.category,
            sequence=rule.sequence,
            amount=amount,
            quantity=quantity,
            rate=rate,
            total=total,
        )

        # حدّث مجاميع الفئات
        categories_sum[rule.category.code] = categories_sum.get(rule.category.code, Decimal("0.00")) + total

    # 4) إحالة gross/net من مجاميع الفئات (اتفاقية بسيطة: BASIC + ALW − DED)
    gross = categories_sum.get("BASIC", Decimal("0.00")) + categories_sum.get("ALW", Decimal("0.00"))
    net = gross - categories_sum.get("DED", Decimal("0.00"))

    # لا تحفظ هنا؛ اترك الحفظ لـ slip.recompute(persist=...)
    slip.basic = categories_sum.get("BASIC", Decimal("0.00"))
    slip.allowances = categories_sum.get("ALW", Decimal("0.00"))
    slip.deductions = categories_sum.get("DED", Decimal("0.00"))
    slip.net = net
    slip.gross_wage = gross
    slip.net_wage = net


def recompute_lines(slip: Payslip, *, persist: bool = True):

    """يحذف السطور ويعيد بنائها بمحرّك القواعد ثم يحدّث المجاميع."""

    if slip.company_id != slip.period.company_id:
        raise ValidationError("Payslip company mismatch with period company.")

    if slip.employee.company_id != slip.company_id:
        raise ValidationError("Payslip company mismatch with employee company.")

    if not slip.struct_id:
        raise ValidationError("Payslip has no structure.")
    _compute_payslip_by_rules(slip)
    slip.recompute(persist=persist)
    return slip


@transaction.atomic
def generate_payslip(employee, period: PayrollPeriod, *, overwrite: bool = False, note: str = "") -> Payslip:
    """
    ابْنِ (أو أعد بناء) قسيمة موظف لفترة معيّنة.
    - إذا كانت الفترة مغلقة: أعد الموجود أو أنشئ هيكلًا فارغًا دون حساب.
    - overwrite=True: يحذف السطور القديمة ويعيد بناءها إذا كانت القسيمة موجودة.
    """
    # لا نسمح بالعمل على فترة مقفلة
    if getattr(period, "state", "open") == "closed":
        slip = Payslip.objects.filter(employee=employee, period=period).first()
        if slip:
            return slip
        # أنشئ سجلاً محفوظًا (بدون حساب سطور)
        return Payslip.objects.create(
            employee=employee, company=period.company, period=period, note=note
        )

    # إنشاء/جلب القسيمة
    slip, created = Payslip.objects.get_or_create(
        employee=employee,
        period=period,
        defaults={"company": period.company, "note": note},
    )

    # إن كانت موجودة مسبقًا
    if not created:
        if not overwrite:
            return slip
        # إعادة البناء: تنظيف السطور القديمة فقط
        slip.lines.all().delete()
        if note:
            slip.note = note

    # لقطة رأس القسيمة (snapshot)
    slip.company = period.company
    if not slip.department_id:
        slip.department = getattr(employee, "department", None)
    if not slip.job_id:
        slip.job = getattr(employee, "job", None)
    slip.save(update_fields=["company", "department", "job", "note"] if note else ["company", "department", "job"])

    # اختيار Structure (الأول في شركة الفترة إذا لم يُحدَّد) + تحقق صريح
    if not slip.struct_id:
        struct = PayrollStructure.objects.filter(company=period.company).order_by("id").first()
        if not struct:
            raise ValidationError("No payroll structure found for this company/period.")
        slip.struct = struct
        slip.save(update_fields=["struct"])

    # شغّل محرّك القواعد (يبني PayslipLine بحسب القواعد والفئات)
    _compute_payslip_by_rules(slip)

    # تحديث المجاميع النهائية من السطور
    slip.recompute(persist=True)
    return slip


@transaction.atomic
def generate_payslips_for_period(period: PayrollPeriod, employees_qs, *, overwrite: bool = False) -> list[Payslip]:
    """
    توليد قسائم لمجموعة موظفين في فترة واحدة (مع احترام الشركة).
    """
    slips: list[Payslip] = []
    if getattr(period, "state", "open") == "closed":
        return []
    for emp in employees_qs.select_related("company", "department", "job"):
        if emp.company_id != period.company_id:
            continue
        slips.append(generate_payslip(emp, period, overwrite=overwrite))
    return slips


# === Seed minimal categories & rules for a given structure ===

def seed_minimal_rules(struct: PayrollStructure):
    if not struct or not struct.pk:
        raise ValidationError("Invalid payroll structure.")

    # 1) Ensure categories (BASIC, ALW, DED)
    cat_map = {}  # code -> category
    for code, name, seq in [("BASIC", "Basic", 10), ("ALW", "Allowances", 20), ("DED", "Deductions", 90)]:
        cat, _ = SalaryRuleCategory.objects.get_or_create(
            company=struct.company,
            code=code,
            defaults={"name": name, "sequence": seq}
        )
        cat_map[code] = cat

    # 2) Ensure rules (sequence: 100, 200, 900)
    defaults = []
    # BASIC
    defaults.append({
        "code": "BASIC",
        "name": "Basic Salary",
        "sequence": 100,
        "category": cat_map["BASIC"],
        "condition_select": "always",
        "condition_python": "result = True",
        "amount_python": "\n".join([
            "amount = BASIC",
            "quantity = 1",
            "rate = 100",
            "total = amount",
        ]),
    })
    # ALW_TRAN (from inputs)
    defaults.append({
        "code": "ALW_TRAN",
        "name": "Transport Allowance",
        "sequence": 200,
        "category": cat_map["ALW"],
        "condition_select": "always",
        "condition_python": "result = True",
        "amount_python": "\n".join([
            "amount = inputs.get('ALW_TRAN', 0)",
            "quantity = 1",
            "rate = 100",
            "total = amount",
        ]),
    })
    # DED_TAX (rate from RuleParameter: TAX_RATE, default 3%)
    defaults.append({
        "code": "DED_TAX",
        "name": "Withholding Tax",
        "sequence": 900,
        "category": cat_map["DED"],
        "condition_select": "always",
        "condition_python": "result = True",
        "amount_python": "\n".join([
            "tax_rate = params.get('TAX_RATE', Decimal('0.03'))",
            "base = (categories.get('BASIC', 0) + categories.get('ALW', 0))",
            "amount = base * tax_rate",
            "quantity = 1",
            "rate = 100",
            "total = amount",
        ]),
    })

    created, skipped = 0, 0
    for vals in defaults:
        obj, was_created = SalaryRule.objects.get_or_create(
            struct=struct,
            code=vals["code"],
            defaults=vals,
        )
        created += int(was_created)
        skipped += int(not was_created)
    return {"created": created, "skipped": skipped}
