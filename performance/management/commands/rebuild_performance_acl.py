# performance/management/commands/rebuild_performance_acl.py
from django.core.management.base import BaseCommand

from base.acl_service import apply_default_acl
from performance import models as m
from performance import signals  # لضمان توفر الدوال المساعدة


class Command(BaseCommand):
    help = "Rebuild default ACLs for all Performance objects (Objectives, KPIs, Tasks, Evaluations, ...)."

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("Rebuilding Performance ACLs ..."))

        models = [
            m.Objective,
            m.KPI,
            m.Task,
            m.EvaluationTemplate,
            m.EvaluationParameter,
            m.Evaluation,
            m.EvaluationParameterResult,
        ]

        for Model in models:
            qs = Model.objects.all()
            self.stdout.write(f"- Processing {Model.__name__}: {qs.count()} records")
            for obj in qs:
                # 1) ACL الافتراضي (مالك + HR + هرمية الأقسام)
                apply_default_acl(obj)

        # 2) استدعاء signals الخاصة بالموظف/المقيّم/assignee على السجلات القديمة
        for obj in m.Objective.objects.all():
            signals.grant_objective_main_people_acl(m.Objective, obj, created=False)

        for obj in m.Task.objects.all():
            signals.grant_task_assignee_acl(m.Task, obj, created=False)

        for obj in m.Evaluation.objects.all():
            signals.grant_evaluation_people_acl(m.Evaluation, obj, created=False)

        self.stdout.write(self.style.SUCCESS("Done rebuilding Performance ACLs."))
