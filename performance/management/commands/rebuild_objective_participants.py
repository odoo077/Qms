# performance/management/commands/rebuild_objective_participants.py

from django.core.management.base import BaseCommand
from performance.models import Objective


class Command(BaseCommand):
    help = "Rebuild Objective participants for all existing objectives."

    def handle(self, *args, **options):
        qs = Objective.objects.all()
        total = qs.count()
        self.stdout.write(f"Rebuilding participants for {total} objectives ...")

        for idx, obj in enumerate(qs, start=1):
            # تستدعي المنطق الداخلي الموجود في الموديل
            obj._rebuild_participants()
            self.stdout.write(f"- [{idx}/{total}] rebuilt for Objective #{obj.id}")

        self.stdout.write(self.style.SUCCESS("Done rebuilding participants for all objectives."))
