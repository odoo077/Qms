# performance/signals/ownership.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from guardian.shortcuts import assign_perm

from performance.models import (
    Objective,
    KPI,
    Task,
    EvaluationTemplate,
    EvaluationParameter,
    Evaluation,
    EvaluationParameterResult,
)

# مَنح صلاحيات معقولة للمنشئ عند الإنشاء (يمكن تعديلها حسب سياساتك)


@receiver(post_save, sender=Objective)
def grant_owner_perms_objective(sender, instance, created, **kwargs):
    user = getattr(instance, "created_by", None)
    if created and user:
        assign_perm("performance.view_objective", user, instance)
        assign_perm("performance.change_objective", user, instance)
        assign_perm("performance.manage_objective_kpis", user, instance)
        assign_perm("performance.manage_objective_tasks", user, instance)
        assign_perm("performance.manage_objective_participants", user, instance)


@receiver(post_save, sender=KPI)
def grant_owner_perms_kpi(sender, instance, created, **kwargs):
    user = getattr(instance, "created_by", None)
    if created and user:
        assign_perm("performance.view_kpi", user, instance)
        assign_perm("performance.change_kpi", user, instance)
        assign_perm("performance.recompute_kpi", user, instance)
        assign_perm("performance.set_kpi_manual_value", user, instance)


@receiver(post_save, sender=Task)
def grant_owner_perms_task(sender, instance, created, **kwargs):
    user = getattr(instance, "created_by", None)
    if created and user:
        assign_perm("performance.view_task", user, instance)
        assign_perm("performance.change_task", user, instance)
        assign_perm("performance.assign_task", user, instance)
        assign_perm("performance.update_task_progress", user, instance)


@receiver(post_save, sender=EvaluationTemplate)
def grant_owner_perms_template(sender, instance, created, **kwargs):
    user = getattr(instance, "created_by", None)
    if created and user:
        assign_perm("performance.view_evaluationtemplate", user, instance)
        assign_perm("performance.change_evaluationtemplate", user, instance)
        assign_perm("performance.use_evaluation_template", user, instance)
        assign_perm("performance.manage_template_parameters", user, instance)


@receiver(post_save, sender=EvaluationParameter)
def grant_owner_perms_parameter(sender, instance, created, **kwargs):
    user = getattr(instance, "created_by", None)
    if created and user:
        assign_perm("performance.view_evaluationparameter", user, instance)
        assign_perm("performance.change_evaluationparameter", user, instance)
        assign_perm("performance.reorder_parameters", user, instance)


@receiver(post_save, sender=Evaluation)
def grant_owner_perms_evaluation(sender, instance, created, **kwargs):
    user = getattr(instance, "created_by", None)
    if created and user:
        assign_perm("performance.view_evaluation", user, instance)
        assign_perm("performance.change_evaluation", user, instance)
        assign_perm("performance.submit_evaluation", user, instance)
        assign_perm("performance.approve_evaluation", user, instance)
        assign_perm("performance.view_confidential_notes", user, instance)


@receiver(post_save, sender=EvaluationParameterResult)
def grant_owner_perms_param_result(sender, instance, created, **kwargs):
    user = getattr(instance, "created_by", None)
    if created and user:
        assign_perm("performance.view_evaluationparameterresult", user, instance)
        assign_perm("performance.change_evaluationparameterresult", user, instance)
        assign_perm("performance.rate_parameter_result", user, instance)

# لم أمنح صلاحيات للـ Assignments/Participants لأنها سجلات “مشتقة/إدارية”، وغالبًا تُدار بالصلاحيات على Objective نفسه.
