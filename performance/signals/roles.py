# performance/signals/roles.py
from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

from performance.models import (
    Objective,
    KPI,
    Task,
    ObjectiveDepartmentAssignment,
    ObjectiveEmployeeAssignment,
    ObjectiveParticipant,
    EvaluationTemplate,
    EvaluationParameter,
    Evaluation,
    EvaluationParameterResult,
)


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
