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
from base.acl_service import grant_access, apply_default_acl
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


# لضمان صلاحيات أولية تلقائية لكل سجل جديد (حتى لو لم يُنشأ من الـ services):
# Default ACLs for key models
@receiver(post_save, sender=Objective)
@receiver(post_save, sender=KPI)
@receiver(post_save, sender=Task)
@receiver(post_save, sender=EvaluationTemplate)
@receiver(post_save, sender=EvaluationParameter)
@receiver(post_save, sender=Evaluation)
@receiver(post_save, sender=EvaluationParameterResult)
def _apply_default_acl_performance(sender, instance, created, **kwargs):
    if created:
        apply_default_acl(instance)
