from django.db.models.signals import post_delete
from django.db.models.signals import post_save
from guardian.shortcuts import assign_perm
from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from performance.models import (
    ObjectiveParticipant,
    EvaluationTemplate,
    EvaluationParameter,
    Evaluation,
    EvaluationParameterResult,
)
from performance.models import (
    Objective, KPI, Task,
    ObjectiveDepartmentAssignment, ObjectiveEmployeeAssignment
)

# -----------------------------
# Participants: rebuild when assignments change
# -----------------------------

from typing import Optional

def _get_objective_safe(obj_id) -> Optional[Objective]:
    if not obj_id:
        return None
    try:
        return Objective.objects.only("id").get(pk=obj_id)
    except Objective.DoesNotExist:
        return None

# -----------------------------
# Participants: rebuild when assignments change
# -----------------------------


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
# Objective aggregations: bubble up on KPI/Task changes
# -----------------------------

def _recompute_objective(obj: Objective):
    # Recompute progress & score and persist (only fields)
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

# Note: We fetch Objective by id inside signals instead of touching instance.objective directly
# because post_delete handlers may run after the related Objective has been removed (cascade),
# and dereferencing `instance.objective` could raise DoesNotExist. Using the id avoids that race.


# ---------- ownership & roles ---------

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


@receiver(post_migrate)
def ensure_performance_roles(sender, **kwargs):
    """
    ينشئ مجموعات الأداء ويُسند لها صلاحيات الموديلات (الافتراضية) + الصلاحيات المخصّصة.
    يُنفَّذ فقط عند ترحيل تطبيق performance.
    """
    if getattr(sender, "name", None) != "performance":
        return

    # مختصر لجلب Permission بالـ codename على موديل معيّن
    def _perm(codename: str, model):
        ct = ContentType.objects.get_for_model(model)
        return Permission.objects.get(codename=codename, content_type=ct)

    # ⬇️ مجموعات مقترحة وقابلة للتعديل حسب فريقك
    GROUPS = {
        # مديرو الأداء: كل شيء تقريبًا
        "Performance Managers": [
            # Objective
            ("view_objective", Objective),
            ("change_objective", Objective),
            ("close_objective", Objective),
            ("manage_objective_participants", Objective),
            ("manage_objective_kpis", Objective),
            ("manage_objective_tasks", Objective),
            # KPI
            ("view_kpi", KPI),
            ("change_kpi", KPI),
            ("recompute_kpi", KPI),
            ("set_kpi_manual_value", KPI),
            # Task
            ("view_task", Task),
            ("change_task", Task),
            ("assign_task", Task),
            ("update_task_progress", Task),
            # Assignments / Participants (قراءة وتعديل إدارياً على التعيينات)
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
            # Template parameters
            ("view_evaluationparameter", EvaluationParameter),
            ("change_evaluationparameter", EvaluationParameter),
            ("reorder_parameters", EvaluationParameter),
            # Evaluation
            ("view_evaluation", Evaluation),
            ("change_evaluation", Evaluation),
            ("submit_evaluation", Evaluation),
            ("approve_evaluation", Evaluation),
            ("view_confidential_notes", Evaluation),
            # Parameter results
            ("view_evaluationparameterresult", EvaluationParameterResult),
            ("change_evaluationparameterresult", EvaluationParameterResult),
            ("rate_parameter_result", EvaluationParameterResult),
        ],

        # موظفو الأداء: صلاحيات تشغيلية بدون صلاحيات إدارية كاملة
        "Performance Officers": [
            # Objective (قراءة عامة)
            ("view_objective", Objective),
            # KPI (قراءة + ضبط يدوي عند الحاجة)
            ("view_kpi", KPI),
            ("set_kpi_manual_value", KPI),
            # Task (قراءة + تحديث تقدّم)
            ("view_task", Task),
            ("update_task_progress", Task),
            # Participants / Assignments (قراءة فقط)
            ("view_objectiveparticipant", ObjectiveParticipant),
            ("view_objectivedepartmentassignment", ObjectiveDepartmentAssignment),
            ("view_objectiveemployeeassignment", ObjectiveEmployeeAssignment),
            # Templates (استخدام القالب فقط)
            ("view_evaluationtemplate", EvaluationTemplate),
            ("use_evaluation_template", EvaluationTemplate),
            ("view_evaluationparameter", EvaluationParameter),
            # Evaluation (قراءة + تسليم)
            ("view_evaluation", Evaluation),
            ("submit_evaluation", Evaluation),
            ("view_evaluationparameterresult", EvaluationParameterResult),
            ("rate_parameter_result", EvaluationParameterResult),
        ],
    }

    for group_name, entries in GROUPS.items():
        group, _ = Group.objects.get_or_create(name=group_name)
        assigned = 0
        for codename, model in entries:
            try:
                perm = _perm(codename, model)
            except Permission.DoesNotExist:
                # قد يحدث إذا لم تُنشأ الصلاحية بعد أول post_migrate؛ ستُستكمل لاحقًا بدون فشل
                continue
            group.permissions.add(perm)
            assigned += 1
        # يمكن طباعة/تسجيل assigned إذا رغبت بالتحقق
