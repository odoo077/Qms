# -*- coding: utf-8 -*-
"""
Signals:
- إعادة بناء المشاركين عند تغيّر تعيينات الأقسام/الموظفين.
- إعادة تجميع الهدف عند تغيّر KPI/Task.
- منح صلاحيات الكائن للمنشئ (Guardian).
- إنشاء مجموعات وصلاحيات افتراضية بعد الترحيل.
"""

from typing import Optional

from django.db.models.signals import post_save, post_delete, post_migrate
from django.dispatch import receiver
from base.acl_service import grant_access
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

from performance.models import (
    Objective, KPI, Task,
    ObjectiveDepartmentAssignment, ObjectiveEmployeeAssignment, ObjectiveParticipant,
    EvaluationTemplate, EvaluationParameter, Evaluation, EvaluationParameterResult,
)

# -----------------------------
# Participants: rebuild on assignments change
# -----------------------------
def _get_objective_safe(obj_id) -> Optional[Objective]:
    if not obj_id:
        return None
    try:
        return Objective.objects.only("id").get(pk=obj_id)
    except Objective.DoesNotExist:
        return None


@receiver(post_save, sender=ObjectiveDepartmentAssignment)
@receiver(post_delete, sender=ObjectiveDepartmentAssignment)
def rebuild_participants_on_dept_assignment_change(sender, instance, **kwargs):
    obj = _get_objective_safe(getattr(instance, "objective_id", None))
    if obj:
        obj._rebuild_participants()


@receiver(post_save, sender=ObjectiveEmployeeAssignment)
@receiver(post_delete, sender=ObjectiveEmployeeAssignment)
def rebuild_participants_on_emp_assignment_change(sender, instance, **kwargs):
    obj = _get_objective_safe(getattr(instance, "objective_id", None))
    if obj:
        obj._rebuild_participants()


# -----------------------------
# Objective aggregations bubble-up
# -----------------------------
def _recompute_objective(obj: Objective):
    obj.recompute_progress_and_score()
    obj.save(update_fields=["progress_pct", "score_pct"])


@receiver(post_save, sender=KPI)
@receiver(post_delete, sender=KPI)
def recompute_objective_on_kpi_change(sender, instance, **kwargs):
    obj = _get_objective_safe(getattr(instance, "objective_id", None))
    if obj:
        _recompute_objective(obj)


@receiver(post_save, sender=Task)
@receiver(post_delete, sender=Task)
def recompute_objective_on_task_change(sender, instance, **kwargs):
    obj = _get_objective_safe(getattr(instance, "objective_id", None))
    if obj:
        _recompute_objective(obj)


# -----------------------------
# Object-level permissions (creator ownership)
# -----------------------------
@receiver(post_save, sender=Objective)
def grant_owner_perms_objective(sender, instance, created, **kwargs):
    user = getattr(instance, "created_by", None)
    if created and user:
        grant_access(
            instance, user=user,
            view=True, change=True, delete=True,  # الأساسية
            extras=["manage_objective_kpis", "manage_objective_tasks", "manage_objective_participants"],
        )


@receiver(post_save, sender=KPI)
def grant_owner_perms_kpi(sender, instance, created, **kwargs):
    user = getattr(instance, "created_by", None)
    if created and user:
        grant_access(
            instance, user=user,
            view=True, change=True, delete=True,
            extras=["recompute_kpi", "set_kpi_manual_value"],
        )


@receiver(post_save, sender=Task)
def grant_owner_perms_task(sender, instance, created, **kwargs):
    user = getattr(instance, "created_by", None)
    if created and user:
        grant_access(
            instance, user=user,
            view=True, change=True, delete=True,
            extras=["assign_task", "update_task_progress"],
        )


@receiver(post_save, sender=EvaluationTemplate)
def grant_owner_perms_template(sender, instance, created, **kwargs):
    user = getattr(instance, "created_by", None)
    if created and user:
        grant_access(
            instance, user=user,
            view=True, change=True, delete=True,
            extras=["use_evaluation_template", "manage_template_parameters"],
        )


@receiver(post_save, sender=EvaluationParameter)
def grant_owner_perms_parameter(sender, instance, created, **kwargs):
    user = getattr(instance, "created_by", None)
    if created and user:
        grant_access(
            instance, user=user,
            view=True, change=True, delete=True,
            extras=["reorder_parameters"],
        )


@receiver(post_save, sender=Evaluation)
def grant_owner_perms_evaluation(sender, instance, created, **kwargs):
    user = getattr(instance, "created_by", None)
    if created and user:
        grant_access(
            instance, user=user,
            view=True, change=True, delete=True, approve=True,  # approve كصلاحية أساسية بالـACL
            extras=["submit_evaluation", "view_confidential_notes"],
        )


@receiver(post_save, sender=EvaluationParameterResult)
def grant_owner_perms_param_result(sender, instance, created, **kwargs):
    user = getattr(instance, "created_by", None)
    if created and user:
        grant_access(
            instance, user=user,
            view=True, change=True, delete=True, rate=True,  # rate كصلاحية أساسية في ACL
            extras=["rate_parameter_result"],  # من باب التوافق إن رغبت بالاسم القديم أيضًا
        )


# -----------------------------
# Default roles/groups after migrate
# -----------------------------
@receiver(post_migrate)
def ensure_performance_roles(sender, **kwargs):
    """
    إنشاء مجموعات افتراضية ومنحها صلاحيات الموديلات + الصلاحيات المخصّصة.
    يُنفَّذ فقط عند ترحيل تطبيق performance.
    """
    if getattr(sender, "name", None) != "performance":
        return

    def _perm(codename: str, model):
        ct = ContentType.objects.get_for_model(model)
        return Permission.objects.get(codename=codename, content_type=ct)

    GROUPS = {
        "Performance Managers": [
            # Objective
            ("view_objective", Objective), ("change_objective", Objective),
            ("close_objective", Objective),
            ("manage_objective_participants", Objective),
            ("manage_objective_kpis", Objective),
            ("manage_objective_tasks", Objective),
            # KPI
            ("view_kpi", KPI), ("change_kpi", KPI),
            ("recompute_kpi", KPI), ("set_kpi_manual_value", KPI),
            # Task
            ("view_task", Task), ("change_task", Task),
            ("assign_task", Task), ("update_task_progress", Task),
            # Assignments / Participants
            ("view_objectivedepartmentassignment", ObjectiveDepartmentAssignment),
            ("change_objectivedepartmentassignment", ObjectiveDepartmentAssignment),
            ("manage_department_assignments", ObjectiveDepartmentAssignment),

            ("view_objectiveemployeeassignment", ObjectiveEmployeeAssignment),
            ("change_objectiveemployeeassignment", ObjectiveEmployeeAssignment),
            ("manage_employee_assignments", ObjectiveEmployeeAssignment),

            ("view_objectiveparticipant", ObjectiveParticipant),
            # Templates
            ("view_evaluationtemplate", EvaluationTemplate),
            ("change_evaluationtemplate", EvaluationTemplate),
            ("use_evaluation_template", EvaluationTemplate),
            ("manage_template_parameters", EvaluationTemplate),
            # Parameters
            ("view_evaluationparameter", EvaluationParameter),
            ("change_evaluationparameter", EvaluationParameter),
            ("reorder_parameters", EvaluationParameter),
            # Evaluation
            ("view_evaluation", Evaluation),
            ("change_evaluation", Evaluation),
            ("submit_evaluation", Evaluation),
            ("approve_evaluation", Evaluation),
            ("view_confidential_notes", Evaluation),
            # Results
            ("view_evaluationparameterresult", EvaluationParameterResult),
            ("change_evaluationparameterresult", EvaluationParameterResult),
            ("rate_parameter_result", EvaluationParameterResult),
        ],
        "Performance Officers": [
            ("view_objective", Objective),
            ("view_kpi", KPI), ("set_kpi_manual_value", KPI),
            ("view_task", Task), ("update_task_progress", Task),
            ("view_objectiveparticipant", ObjectiveParticipant),
            ("view_objectivedepartmentassignment", ObjectiveDepartmentAssignment),
            ("view_objectiveemployeeassignment", ObjectiveEmployeeAssignment),
            ("view_evaluationtemplate", EvaluationTemplate),
            ("use_evaluation_template", EvaluationTemplate),
            ("view_evaluationparameter", EvaluationParameter),
            ("view_evaluation", Evaluation), ("submit_evaluation", Evaluation),
            ("view_evaluationparameterresult", EvaluationParameterResult),
            ("rate_parameter_result", EvaluationParameterResult),
        ],
    }

    for group_name, entries in GROUPS.items():
        group, _ = Group.objects.get_or_create(name=group_name)
        for codename, model in entries:
            try:
                perm = _perm(codename, model)
            except Permission.DoesNotExist:
                continue
            group.permissions.add(perm)
