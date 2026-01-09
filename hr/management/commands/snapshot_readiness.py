from django.core.management.base import BaseCommand
from django.utils import timezone

from hr.models import Employee
from skills.services import create_employee_readiness_snapshot


class Command(BaseCommand):
    help = "Create/update Employee Readiness snapshots (daily/weekly job)."

    def add_arguments(self, parser):
        parser.add_argument("--date", type=str, default=None, help="Snapshot date YYYY-MM-DD (default: today)")
        parser.add_argument("--company-id", type=int, default=None, help="Limit to one company")
        parser.add_argument("--employee-id", type=int, default=None, help="Limit to one employee")
        parser.add_argument("--include-inactive", action="store_true", help="Include inactive employees")

    def handle(self, *args, **options):
        date_str = options.get("date")
        company_id = options.get("company_id")
        employee_id = options.get("employee_id")
        include_inactive = options.get("include_inactive")

        snapshot_date = timezone.localdate()
        if date_str:
            snapshot_date = timezone.datetime.fromisoformat(date_str).date()

        qs = Employee.objects.all().select_related("company", "job")

        if not include_inactive:
            qs = qs.filter(active=True)

        if company_id:
            qs = qs.filter(company_id=company_id)

        if employee_id:
            qs = qs.filter(id=employee_id)

        count = 0
        for emp in qs.iterator():
            # Hard guard: employee must have company
            if not emp.company_id:
                continue
            create_employee_readiness_snapshot(emp, snapshot_date=snapshot_date)
            count += 1

        self.stdout.write(self.style.SUCCESS(f"Readiness snapshots upserted: {count} (date={snapshot_date})"))
