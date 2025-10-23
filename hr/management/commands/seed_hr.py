# hr/management/commands/seed_hr.py
# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.apps import apps
from datetime import date

# ------------- Helpers -------------

from django.db.models.fields import NOT_PROVIDED

def pick_location_type_value(WorkLocation):
    """
    يرجّع قيمة صالحة لحقل location_type:
    - إن كان له default: نستخدمه.
    - وإلا إن كان له LocationType (TextChoices): نحاول OFFICE، ثم أول اختيار.
    - وإلا من choices للحقل: أول اختيار.
    """
    # جرّب default من الحقل نفسه
    f = WorkLocation._meta.get_field("location_type")
    if f.default is not NOT_PROVIDED:
        return f.default() if callable(f.default) else f.default

    # جرّب enum TextChoices، إن وُجد
    if hasattr(WorkLocation, "LocationType"):
        LT = WorkLocation.LocationType
        # حاول OFFICE/Office/office
        for attr in ("OFFICE", "Office", "office"):
            if hasattr(LT, attr):
                return getattr(LT, attr)
        # وإلا أول عنصر من LT
        try:
            return list(LT)[0].value
        except Exception:
            pass

    # جرّب choices على الحقل
    choices = getattr(f, "choices", None) or []
    if choices:
        # كل عنصر (value, label)
        return choices[0][0]

    # آخر حل: قيمة نصية عامة (قد تفشل إن لم تكن ضمن choices)
    return "office"

def M(app_label, model_name):
    return apps.get_model(app_label, model_name)

def get_field(obj_or_model, *candidates):
    """
    يرجّع أول اسم حقل موجود من مجموعة مرشّحات (لمواءمة اختلاف التسميات).
    يقبل كلا: الكائن أو الصنف.
    """
    model = obj_or_model if isinstance(obj_or_model, type) else obj_or_model.__class__
    for n in candidates:
        try:
            model._meta.get_field(n)
            return n
        except Exception:
            continue
    return None

def set_m2m(obj, field_name, values):
    if not field_name:
        return
    getattr(obj, field_name).set(values)

def ensure_child_partner(company, name, parent_partner=None, **extra_defaults):
    """
    ينشئ/يعيد Partner (contact) تحت Partner الشركة — Odoo-like.
    """
    Partner = M("base", "Partner")
    if parent_partner is None and hasattr(company, "partner_id") and company.partner_id:
        parent_partner = company.partner

    p, created = Partner.objects.get_or_create(
        name=name,
        defaults={
            "is_company": False,
            "type": "contact",
            "company": company if get_field(Partner, "company") else None,
            "parent": parent_partner if get_field(Partner, "parent") else None,
            **extra_defaults,
        },
    )
    changed = False
    if get_field(Partner, "company") and not getattr(p, "company_id", None):
        p.company = company
        changed = True
    if get_field(Partner, "parent") and parent_partner and getattr(p, "parent_id", None) != parent_partner.id:
        p.parent = parent_partner
        changed = True
    if changed:
        p.save()
    return p

def get_company_by_name(name):
    Company = M("base", "Company")
    comp = Company.objects.filter(name=name).first()
    if not comp:
        raise CommandError(f'Company "{name}" not found in app "base". Create it first.')
    return comp

# ------------- Command -------------
class Command(BaseCommand):
    help = "Seed HR data for the listed HR models only: Work locations, Departments, Jobs, Contract types, Employee categories, Employees."

    def add_arguments(self, parser):
        parser.add_argument("--company", default="Ahlan Holding", help='Target company name (default: "Ahlan Holding").')
        parser.add_argument("--dry-run", action="store_true", help="Simulate without writing to DB.")

    @transaction.atomic
    def handle(self, *args, **opts):
        company_name = opts["company"]
        dry = opts["dry_run"]

        # --- Resolve models present in your HR app (only those shown in the screenshot)
        WorkLocation   = M("hr", "WorkLocation")
        Department     = M("hr", "Department")
        Job            = M("hr", "Job")
        ContractType   = M("hr", "ContractType")
        EmployeeCat    = M("hr", "EmployeeCategory")
        Employee       = M("hr", "Employee")
        Partner        = M("base", "Partner")
        Company        = M("base", "Company")

        company = get_company_by_name(company_name)
        comp_partner = getattr(company, "partner", None)

        self.stdout.write(self.style.NOTICE(f">> Seeding HR for company: {company.name}"))

        # ---------- 1) Work Locations ----------
        self.stdout.write("-> Work Locations")
        # حاول استعمال Address كـ Partner (Odoo-like). لو ما عندك الحقل، نتجاوز ربط العنوان.
        wl_address_field = get_field(WorkLocation, "address", "address_id")
        wl_locnum_field  = get_field(WorkLocation, "location_number")
        wl_loctype_field = get_field(WorkLocation, "location_type")
        wl_company_field = get_field(WorkLocation, "company")

        wloc_defs = [
            {"name": "HQ Baghdad",   "number": "HQ-BGD", "address_name": "HQ Baghdad Address"},
            {"name": "Basra POP",    "number": "POP-BSR","address_name": "Basra POP Address"},
            {"name": "Warehouse 01", "number": "WH-01",  "address_name": "Warehouse 01 Address"},
        ]
        worklocs = {}
        for d in wloc_defs:
            defaults = {"active": True}
            if wl_company_field:
                defaults[wl_company_field] = company
            if wl_locnum_field:
                defaults[wl_locnum_field] = d["number"]
            if wl_loctype_field:
                defaults[wl_loctype_field] = pick_location_type_value(WorkLocation)
            # عنوان كشريك طفل تحت شركة
            if wl_address_field:
                addr = ensure_child_partner(company, d["address_name"], parent_partner=comp_partner)
                defaults[wl_address_field] = addr

            wl, _ = WorkLocation.objects.get_or_create(name=d["name"], **({wl_company_field: company} if wl_company_field else {}), defaults=defaults)
            worklocs[d["name"]] = wl

        # ---------- 2) Departments (Hierarchy) ----------
        self.stdout.write("-> Departments (Division > Department > Section > Team)")
        dept_company_field = get_field(Department, "company")
        dept_parent_field  = get_field(Department, "parent")

        tree = [
            ("Network Operations", [
                ("NOC", [
                    ("NOC L1", [("NOC Night Shift", [])]),
                    ("NOC L2", []),
                ]),
                ("Field Operations", [
                    ("Field North", []),
                    ("Field South", []),
                ]),
                ("FTTH Deployment", [
                    ("FTTH Survey Team", []),
                ]),
            ]),
            ("Customer Care", [
                ("Contact Center", [
                    ("CC Outbound", []),
                    ("CC Inbound", []),
                ]),
            ]),
            ("Sales & Marketing", [
                ("Corporate Sales", []),
                ("Digital Marketing", []),
            ]),
            ("Finance & Admin", [
                ("Accounting", []),
                ("HR & Payroll", []),
            ]),
        ]

        def ensure_dep(name, parent=None):
            kwargs = {"name": name}
            if dept_company_field:
                kwargs[dept_company_field] = company
            if dept_parent_field:
                kwargs[dept_parent_field] = parent
            dep, _ = Department.objects.get_or_create(**kwargs)
            return dep

        def build(nodes, parent=None):
            for name, children in nodes:
                node = ensure_dep(name, parent)
                for child in children:
                    build([child], node)

        build(tree, None)
        dep_map = {d.name: d for d in Department.objects.filter(**({dept_company_field: company} if dept_company_field else {}))}

        # ---------- 3) Job Positions ----------
        self.stdout.write("-> Jobs")
        job_company_field   = get_field(Job, "company")
        job_dept_field      = get_field(Job, "department")
        job_expected_field  = get_field(Job, "expected_employees")

        job_defs = [
            ("NOC Engineer",         "NOC",             10),
            ("Senior NOC Engineer",  "NOC",              3),
            ("Field Technician",     "Field Operations",25),
            ("FTTH Surveyor",        "FTTH Deployment",  6),
            ("Contact Center Agent", "Contact Center",  50),
            ("Sales Executive",      "Corporate Sales", 12),
            ("Digital Marketer",     "Digital Marketing",4),
            ("Accountant",           "Accounting",       5),
            ("HR Specialist",        "HR & Payroll",     3),
        ]

        jobs = {}
        for name, dname, expected in job_defs:
            dep = dep_map.get(dname)
            if not dep:
                raise CommandError(f"Department not found for job: {dname}")
            kwargs = {"name": name}
            if job_company_field:
                kwargs[job_company_field] = company
            if job_dept_field:
                kwargs[job_dept_field] = dep

            defaults = {}
            if job_expected_field:
                defaults[job_expected_field] = expected

            job, _ = Job.objects.get_or_create(**kwargs, defaults=defaults)
            # Ensure expected if field exists and empty
            if job_expected_field and not getattr(job, job_expected_field):
                setattr(job, job_expected_field, expected)
                job.save(update_fields=[job_expected_field])
            jobs[name] = job

        # ---------- 4) Contract Types ----------
        self.stdout.write("-> Contract types")
        ct_company_field = get_field(ContractType, "company")
        ct_code_field    = get_field(ContractType, "code")

        ct_defs = [
            ("Permanent",  "PERM"),
            ("Internship", "INT"),
            ("Contractor", "CONT"),
        ]
        for name, code in ct_defs:
            kwargs = {"name": name}
            if ct_company_field:
                kwargs[ct_company_field] = company
            defaults = {}
            if ct_code_field:
                defaults[ct_code_field] = code
            ContractType.objects.get_or_create(**kwargs, defaults=defaults)

        # ---------- 5) Employee Categories ----------
        self.stdout.write("-> Employee categories")
        cat_company_field = get_field(EmployeeCat, "company")

        cat_names = ["Crew – FTTH", "NOC – Night Shift", "Sales – Corporate", "Contact Center – KPI"]
        cats = {}
        for cname in cat_names:
            kwargs = {"name": cname}
            if cat_company_field:
                kwargs[cat_company_field] = company
            c, _ = EmployeeCat.objects.get_or_create(**kwargs)
            cats[cname] = c

        # ---------- 6) Employees ----------
        self.stdout.write("-> Employees")
        emp_company_field   = get_field(Employee, "company")
        emp_dept_field      = get_field(Employee, "department")
        emp_job_field       = get_field(Employee, "job")
        emp_wloc_field      = get_field(Employee, "work_location", "work_location_id")
        emp_wc_field        = get_field(Employee, "work_contact", "address_home", "address_home_id")
        emp_barcode_field   = get_field(Employee, "barcode")
        emp_pin_field       = get_field(Employee, "pin")
        emp_cats_field      = get_field(Employee, "categories", "category", "category_ids")
        emp_manager_field   = get_field(Employee, "parent", "manager")
        emp_coach_field     = get_field(Employee, "coach")

        emp_defs = [
            ("Ali Kareem Mohammed",   "NOC",            "Senior NOC Engineer", "HQ Baghdad",  "EMP-AH-0001", "1001", []),
            ("Dina Al-Taie",          "NOC L1",         "NOC Engineer",        "HQ Baghdad",  "EMP-AH-0002", "1002", ["NOC – Night Shift"]),
            ("Hassan Jabar",          "NOC L1",         "NOC Engineer",        "HQ Baghdad",  "EMP-AH-0003", "1003", ["NOC – Night Shift"]),
            ("Mustafa Salman",        "Field South",    "Field Technician",    "Basra POP",   "EMP-AH-0004", "2001", ["Crew – FTTH"]),
            ("Zahraa Abdulzahra",     "FTTH Deployment","FTTH Surveyor",       "Basra POP",   "EMP-AH-0005", "2002", ["Crew – FTTH"]),
            ("Rasha Ahmed",           "CC Outbound",    "Contact Center Agent","HQ Baghdad",  "EMP-AH-0006", "3001", ["Contact Center – KPI"]),
            ("Omar Nasser",           "Corporate Sales","Sales Executive",     "HQ Baghdad",  "EMP-AH-0007", "4001", ["Sales – Corporate"]),
        ]

        employees = {}
        for name, dep_name, job_name, wl_name, barcode, pin, cat_names in emp_defs:
            dep = dep_map[dep_name]
            job = jobs[job_name]
            wl  = worklocs[wl_name]

            kwargs = {"name": name}
            defaults = {}

            if emp_company_field:
                kwargs[emp_company_field] = company
                defaults[emp_company_field] = company
            if emp_dept_field:
                defaults[emp_dept_field] = dep
            if emp_job_field:
                defaults[emp_job_field] = job
            if emp_barcode_field:
                defaults[emp_barcode_field] = barcode
            if emp_pin_field:
                defaults[emp_pin_field] = pin
            if emp_wloc_field:
                defaults[emp_wloc_field] = wl

            # أنشئ/استخدم work_contact كشريك ابن للشركة
            wc_partner = ensure_child_partner(company, name, parent_partner=comp_partner)
            if emp_wc_field:
                defaults[emp_wc_field] = wc_partner

            emp, _ = Employee.objects.get_or_create(**kwargs, defaults=defaults)

            # م2م التصنيفات
            if emp_cats_field:
                selected = [cats[c] for c in cat_names if c in cats]
                set_m2m(emp, emp_cats_field, selected)

            employees[name] = emp

        # علاقات المدير/المدرب (إن وجدت الحقول)
        if emp_manager_field:
            employees["Dina Al-Taie"].__setattr__(emp_manager_field, employees["Ali Kareem Mohammed"])
            employees["Dina Al-Taie"].save(update_fields=[emp_manager_field])
            employees["Hassan Jabar"].__setattr__(emp_manager_field, employees["Dina Al-Taie"])
            employees["Hassan Jabar"].save(update_fields=[emp_manager_field])
        if emp_coach_field:
            employees["Hassan Jabar"].__setattr__(emp_coach_field, employees["Dina Al-Taie"])
            employees["Hassan Jabar"].save(update_fields=[emp_coach_field])

        # ملاحظة: EmployeePublic عادة VIEW (managed=False) فلا نُلِمّه ببيانات.

        if dry:
            self.stdout.write(self.style.WARNING("Dry-run enabled — rolling back."))
            raise transaction.TransactionManagementError("Dry-run rollback")

        self.stdout.write(self.style.SUCCESS("HR seed completed successfully."))
