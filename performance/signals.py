# performance/signals.py
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
from performance.models import (
    Objective, KPI, Task,
    ObjectiveDepartmentAssignment, ObjectiveEmployeeAssignment, ObjectiveParticipant,
    EvaluationTemplate, EvaluationParameter, Evaluation, EvaluationParameterResult,
)
from . import models as m


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


@receiver(post_save, sender=m.Objective)
def grant_objective_main_people_acl(sender, instance: m.Objective, created: bool, **kwargs):
    """
    - يمنح target_employee صلاحيات مناسبة لرؤية هدفه.
    - يمنح reviewer صلاحيات إدارة الهدف.
    """
    from base.acl_service import grant_access

    # 1) الموظف المستهدف Target Employee
    target_emp = getattr(instance, "target_employee", None)
    if target_emp and target_emp.user_id:
        grant_access(
            instance,
            user=target_emp.user,
            view=True,
            comment=True,     # employee can add notes
        )

    # 2) المراجع Reviewer (عادة المدير المباشر)
    reviewer = getattr(instance, "reviewer", None)
    if reviewer and reviewer.user_id:
        grant_access(
            instance,
            user=reviewer.user,
            view=True,
            change=True,
            comment=True,
            approve=True,     # اعتماد الهدف
        )


@receiver(post_save, sender=m.Task)
def grant_task_assignee_acl(sender, instance: m.Task, created: bool, **kwargs):
    """
    يمنح المكلّف بالمهمة صلاحيات مناسبة على الـ Task.
    """
    from base.acl_service import grant_access

    emp = getattr(instance, "assignee", None)
    if emp and emp.user_id:
        grant_access(
            instance,
            user=emp.user,
            view=True,
            change=True,     # لتحديث progress
            comment=True,    # لإضافة ملاحظات
        )


@receiver(post_save, sender=m.Evaluation)
def grant_evaluation_people_acl(sender, instance: m.Evaluation, created: bool, **kwargs):
    """
    - الموظف الذي يتم تقييمه: يرى تقييمه ويضع ملاحظات.
    - المقيّم Evaluator: يدير التقييم ويوافق عليه.
    """
    from base.acl_service import grant_access

    # 1) الموظف الذي يتم تقييمه
    emp = getattr(instance, "employee", None)
    if emp and emp.user_id:
        grant_access(
            instance,
            user=emp.user,
            view=True,
            comment=True,   # يضيف ملاحظات
        )

    # 2) المقيّم (غالباً المدير)
    evaluator = getattr(instance, "evaluator", None)
    if evaluator and evaluator.user_id:
        grant_access(
            instance,
            user=evaluator.user,
            view=True,
            change=True,
            comment=True,
            approve=True,   # اعتماد التقييم
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
