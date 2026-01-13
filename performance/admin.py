# performance/admin.py
"""
لوحة الإدارة — مستثناة من صلاحيات الكائن عبر AppAdmin (مثل بقية التطبيقات).
"""

from django.contrib import admin, messages
from django.db import transaction
from base.admin_mixins import AppAdmin  # ✅ الاستثناء من صلاحيات الكائن

from performance.models import (
    Objective,
    KPI,
    Task,
    ObjectiveDepartmentAssignment,
    ObjectiveEmployeeAssignment,
    ObjectiveParticipant,
    EvaluationType,
    EvaluationApprovalStep,
    EvaluationTemplate,
    EvaluationParameter,
    Evaluation,
    EvaluationParameterResult, EmployeeObjectiveScore, DailyRating, DailyRatingItem, DailyRatingFactor,
    EvaluationExceptionAdjustment, PerformanceException, PerformanceExceptionType, QualityIncident, EvaluationFeedback,
    EvaluationCalibration, EmployeeObjectiveScoringPolicy, ObjectiveCategory, ObjectiveType, ObjectiveStatus, KPIType,
    KPICategory, KPICalculationMethod, TaskProgressPolicy, TaskSLAPolicy, TaskCategory, TaskType, TaskStatus,
    TaskDependency, TaskWatcher, TaskRecurringDefinition,
)


USE_AUTOCOMPLETE = True

# أكشنات عامة
@admin.action(description="Activate selected records")
def action_activate(modeladmin, request, queryset):
    messages.success(request, f"Activated {queryset.update(active=True)} record(s).")

@admin.action(description="Deactivate selected records")
def action_deactivate(modeladmin, request, queryset):
    messages.success(request, f"Deactivated {queryset.update(active=False)} record(s).")


# -------- Inlines (Objective) --------
class ObjectiveDepartmentAssignmentInline(admin.TabularInline):
    model = ObjectiveDepartmentAssignment
    extra = 0
    fields = ["department", "include_children"]
    if USE_AUTOCOMPLETE: autocomplete_fields = ["department"]
    else:                 raw_id_fields = ["department"]
    fk_name = "objective"

class ObjectiveEmployeeAssignmentInline(admin.TabularInline):
    model = ObjectiveEmployeeAssignment
    extra = 0
    fields = ["employee"]
    if USE_AUTOCOMPLETE: autocomplete_fields = ["employee"]
    else:                 raw_id_fields = ["employee"]
    fk_name = "objective"

class ObjectiveParticipantInline(admin.TabularInline):
    model = ObjectiveParticipant
    extra = 0
    can_delete = False
    fields = ["employee"]
    readonly_fields = ["employee", "objective"]
    if USE_AUTOCOMPLETE: autocomplete_fields = ["employee"]
    else:                 raw_id_fields = ["employee"]
    def has_add_permission(self, *a, **kw): return False
    def has_change_permission(self, *a, **kw): return False

class KPIInline(admin.TabularInline):
    model = KPI
    extra = 0
    fields = ["name","unit","higher_is_better","target_value","baseline_value","current_value",
              "weight_pct","attainment_pct","score_pct","active"]
    readonly_fields = ["attainment_pct","score_pct"]

class TaskInline(admin.TabularInline):
    model = Task
    extra = 0
    fields = [
        "title", "assignee", "status", "percent_complete", "due_date", "kpi", "task_kind",
         "estimated_minutes", "actual_minutes", "quality_score_pct", "active"
    ]
    if USE_AUTOCOMPLETE: autocomplete_fields = ["assignee","kpi"]
    else:                 raw_id_fields = ["assignee","kpi"]


# ------------------------------------------------------------
# ObjectiveStatus Admin
# ------------------------------------------------------------

@admin.register(ObjectiveStatus)
class ObjectiveStatusAdmin(AppAdmin):
    """
    إدارة حالات الأهداف (Global) من لوحة الإدارة.
    """

    list_display = (
        "id",
        "code",
        "name",
        "sequence",
        "active",
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
    )
    list_filter = ("active",)
    search_fields = ("code", "name", "description")
    ordering = ("sequence", "code")

    readonly_fields = ("created_at", "updated_at", "created_by", "updated_by")


# ------------------------------------------------------------
# ObjectiveType Admin
# ------------------------------------------------------------

@admin.register(ObjectiveType)
class ObjectiveTypeAdmin(AppAdmin):
    """
    أنواع الأهداف (Global): Quality, Productivity, Operations, ...
    يمكن ربط نوع الهدف بسياسة احتساب افتراضية.
    """

    list_display = (
        "id",
        "code",
        "name",
        "default_scoring_policy",
        "active",
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
    )
    list_filter = ("active",)
    search_fields = ("code", "name", "description")
    ordering = ("code",)

    raw_id_fields = ("default_scoring_policy",)

    readonly_fields = ("created_at", "updated_at", "created_by", "updated_by")


# ------------------------------------------------------------
# ObjectiveCategory Admin
# ------------------------------------------------------------

@admin.register(ObjectiveCategory)
class ObjectiveCategoryAdmin(AppAdmin):
    """
    تصنيفات الأهداف (Global): Strategic, Operational, Development, ...
    تُستخدم للتحليل والتقارير.
    """

    list_display = (
        "id",
        "code",
        "name",
        "active",
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
    )
    list_filter = ("active",)
    search_fields = ("code", "name", "description")
    ordering = ("code",)

    readonly_fields = ("created_at", "updated_at", "created_by", "updated_by")


# ------------------------------------------------------------
# Objective Inlines
# ------------------------------------------------------------

class ObjectiveDepartmentAssignmentInline(admin.TabularInline):
    model = ObjectiveDepartmentAssignment
    extra = 0
    raw_id_fields = ("department",)
    can_delete = True


class ObjectiveEmployeeAssignmentInline(admin.TabularInline):
    model = ObjectiveEmployeeAssignment
    extra = 0
    raw_id_fields = ("employee",)
    can_delete = True


class ObjectiveParticipantInline(admin.TabularInline):
    model = ObjectiveParticipant
    extra = 0
    raw_id_fields = ("employee",)
    can_delete = False
    readonly_fields = ("employee",)


class ObjectiveKPIInline(admin.TabularInline):
    model = KPI
    extra = 0
    raw_id_fields = ("company",)


class ObjectiveTaskInline(admin.TabularInline):
    model = Task
    extra = 0
    raw_id_fields = ("company", "assignee", "kpi")


# ------------------------------------------------------------
# Objective Admin
# ------------------------------------------------------------

@admin.register(Objective)
class ObjectiveAdmin(AppAdmin):
    """
    إدارة الأهداف: إعداد الهرمية، النوع، التصنيف، النطاق، المشاركين، والسياسات.
    """

    list_display = (
        "id",
        "company",
        "code",
        "title",
        "objective_type",
        "category",
        "parent",
        "hierarchy_level",
        "rollup_strategy",
        "date_start",
        "date_end",
        "status",
        "target_kind",
        "target_department",
        "target_employee",
        "weight_pct",
        "progress_pct",
        "score_pct",
        "active",
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
    )

    list_filter = (
        "company",
        "objective_type",
        "category",
        "status",
        "target_kind",
        "active",
        "date_start",
        "date_end",
        "created_at",
        "updated_at",
    )

    search_fields = ("code", "title", "description")

    ordering = ("-date_start", "-id")

    raw_id_fields = (
        "company",
        "reviewer",
        "parent",
        "target_department",
        "target_employee",
        "scoring_policy",
        "objective_type",
        "category",
    )

    readonly_fields = ("created_at", "updated_at", "created_by", "updated_by")

    inlines = [
        ObjectiveDepartmentAssignmentInline,
        ObjectiveEmployeeAssignmentInline,
        ObjectiveParticipantInline,
        ObjectiveKPIInline,
        ObjectiveTaskInline,
    ]


# -------- KPI --------

@admin.register(KPIType)
class KPITypeAdmin(AppAdmin):
    list_display  = ("name", "code", "active")
    search_fields = ("name", "code", "description")
    list_filter   = ("active",)
    ordering      = ("name",)


@admin.register(KPICategory)
class KPICategoryAdmin(AppAdmin):
    list_display  = ("name", "code", "active")
    search_fields = ("name", "code", "description")
    list_filter   = ("active",)
    ordering      = ("name",)


@admin.register(KPICalculationMethod)
class KPICalculationMethodAdmin(AppAdmin):
    list_display  = (
        "name",
        "code",
        "formula_type",
        "green_threshold_pct",
        "yellow_threshold_pct",
        "active",
    )
    list_filter   = ("formula_type", "active")
    search_fields = ("name", "code", "description")
    ordering      = ("name",)


@admin.register(KPI)
class KPIAdmin(AppAdmin):
    """
    إدارة KPIs مع عرض النوع، التصنيف، طريقة الحساب، المالك، ومصدر البيانات.
    """

    list_display = (
        "id",
        "company",
        "objective",
        "name",
        "kpi_type",
        "category",
        "calculation_method",
        "unit",
        "higher_is_better",
        "target_value",
        "current_value",
        "weight_pct",
        "attainment_pct",
        "score_pct",
        "data_source",
        "owner",
        "is_locked",
        "active",
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
    )

    list_filter = (
        "company",
        "objective",
        "kpi_type",
        "category",
        "calculation_method",
        "unit",
        "higher_is_better",
        "data_source",
        "is_locked",
        "active",
        "created_at",
        "updated_at",
    )

    search_fields = (
        "name",
        "description",
        "external_source_ref",
        "objective__title",
        "company__name",
        "owner__name",
    )

    ordering = ("-created_at", "-id")

    if USE_AUTOCOMPLETE:
        autocomplete_fields = [
            "company",
            "objective",
            "owner",
            "kpi_type",
            "category",
            "calculation_method",
        ]
    else:
        raw_id_fields = [
            "company",
            "objective",
            "owner",
            "kpi_type",
            "category",
            "calculation_method",
        ]

    readonly_fields = ("created_at", "updated_at", "created_by", "updated_by")

    actions = ["action_recompute_kpis", action_activate, action_deactivate]


    @admin.action(description="Recompute selected KPIs")
    def action_recompute_kpis(self, request, queryset):
        """
        إعادة احتساب KPIs المختارة باستخدام منطق الموديل،
        مع احترام is_locked وعدم التلاعب بالقيم المجمدة.
        """
        from django.db import transaction
        from django.contrib import messages

        updated = 0
        with transaction.atomic():
            # استخدام select_related لتقليل عدد الاستعلامات على objective
            for kpi in queryset.select_related("objective"):
                if kpi.is_locked:
                    continue
                # save() داخلياً سيستدعي recompute() ويحدث الـ Objective
                kpi.save()
                updated += 1

        messages.success(request, f"Recomputed {updated} KPI(s).")



# -------- Task --------
# ----------------------------------------------------------------------
# TaskStatus
# ----------------------------------------------------------------------
@admin.register(TaskStatus)
class TaskStatusAdmin(AppAdmin):
    list_display = ("name", "code", "sequence", "active")
    ordering = ("sequence", "name")
    search_fields = ("name", "code")
    list_filter = ("active",)


# ----------------------------------------------------------------------
# TaskType
# ----------------------------------------------------------------------
@admin.register(TaskType)
class TaskTypeAdmin(AppAdmin):
    list_display = ("name", "code", "active")
    search_fields = ("name", "code")
    list_filter = ("active",)


# ----------------------------------------------------------------------
# TaskCategory
# ----------------------------------------------------------------------
@admin.register(TaskCategory)
class TaskCategoryAdmin(AppAdmin):
    list_display = ("name", "code", "active")
    search_fields = ("name", "code")
    list_filter = ("active",)


# ----------------------------------------------------------------------
# TaskSLAPolicy
# ----------------------------------------------------------------------
@admin.register(TaskSLAPolicy)
class TaskSLAPolicyAdmin(AppAdmin):
    list_display = (
        "name",
        "code",
        "on_time_pct",
        "mild_delay_pct",
        "severe_delay_pct",
        "allow_blocked_external_no_penalty",
        "active",
    )
    list_filter = ("active",)
    search_fields = ("name", "code")


# ----------------------------------------------------------------------
# TaskProgressPolicy
# ----------------------------------------------------------------------
@admin.register(TaskProgressPolicy)
class TaskProgressPolicyAdmin(AppAdmin):
    list_display = ("name", "code", "active")
    list_filter = ("active",)
    search_fields = ("name", "code")


# ------------------------------------------------------------
# Recurring Task Definition
# ------------------------------------------------------------

@admin.register(TaskRecurringDefinition)
class TaskRecurringDefinitionAdmin(AppAdmin):

    list_display = (
        "id",
        "company",
        "name",
        "code",
        "schedule_kind",
        "task_type",
        "task_category",
        "progress_policy",
        "sla_policy",
        "objective",
        "department",
        "target_count",
        "active",
        "created_at",
    )

    list_filter = (
        "company",
        "schedule_kind",
        "task_type",
        "task_category",
        "active",
        "department",
        "objective",
    )

    search_fields = ("name", "code", "description")

    if USE_AUTOCOMPLETE:
        autocomplete_fields = [
            "company",
            "task_type",
            "task_category",
            "progress_policy",
            "sla_policy",
            "objective",
            "department",
            "excluded_employees",
        ]
    else:
        raw_id_fields = [
            "company",
            "task_type",
            "task_category",
            "progress_policy",
            "sla_policy",
            "objective",
            "department",
            "excluded_employees",
        ]

    readonly_fields = ("created_at", "updated_at", "created_by", "updated_by")
    ordering = ("name", "code")

# ------------------------------------------------------------
# Task Watchers Inline + Admin
# ------------------------------------------------------------

@admin.register(TaskWatcher)
class TaskWatcherAdmin(AppAdmin):
    list_display = ("task", "employee", "active", "created_at")
    list_filter = ("active", "task", "employee")
    search_fields = ("task__title", "employee__name")
    ordering = ("-created_at",)

    if USE_AUTOCOMPLETE:
        autocomplete_fields = ["company", "task", "employee"]
    else:
        raw_id_fields = ["company", "task", "employee"]


# ------------------------------------------------------------
# Task Dependency Admin
# ------------------------------------------------------------

@admin.register(TaskDependency)
class TaskDependencyAdmin(AppAdmin):
    list_display = ("task", "depends_on", "active", "created_at")
    list_filter = ("active",)
    search_fields = ("task__title", "depends_on__title")

    ordering = ("-created_at",)

    if USE_AUTOCOMPLETE:
        autocomplete_fields = ["company", "task", "depends_on"]
    else:
        raw_id_fields = ["company", "task", "depends_on"]


# ----------------------------------------------------------------------
# Inline: Task Watchers
# ----------------------------------------------------------------------
class TaskWatcherInline(admin.TabularInline):
    model = TaskWatcher
    extra = 0
    autocomplete_fields = ["employee"]


# ----------------------------------------------------------------------
# Inline: Task Dependencies (Subtasks / Blocking)
# ----------------------------------------------------------------------
class TaskDependencyInline(admin.TabularInline):
    model = TaskDependency
    fk_name = "task"
    extra = 0
    autocomplete_fields = ["depends_on"]


# ----------------------------------------------------------------------
# TASK ADMIN (FINAL VERSION)
# ----------------------------------------------------------------------
@admin.register(Task)
class TaskAdmin(AppAdmin):

    list_display = (
        "id",
        "company",
        "objective",
        "title",
        "assignee",
        "status",
        "percent_complete",
        "due_date",
        "task_type",
        "task_category",
        "estimated_minutes",
        "actual_minutes",
        "quality_score_pct",
        "active",
        "created_at",
        "updated_at",
    )

    list_filter = (
        "company",
        "status",
        "task_type",
        "task_category",
        "due_date",
        "objective",
        "active",
        "created_at",
        "updated_at",
    )

    search_fields = ("title", "description")

    ordering = ("-id",)

    # Best practice: use autocomplete if enabled
    if USE_AUTOCOMPLETE:
        autocomplete_fields = [
            "company",
            "objective",
            "assignee",
            "kpi",
            "task_type",
            "task_category",
            "progress_policy",
            "sla_policy",
        ]
    else:
        raw_id_fields = [
            "company",
            "objective",
            "assignee",
            "kpi",
            "task_type",
            "task_category",
            "progress_policy",
            "sla_policy",
        ]

    readonly_fields = (
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
        "started_at",
        "completed_at",
    )

    actions = [
        action_activate,
        action_deactivate,
        "recompute_selected_tasks",
    ]

    inlines = [
        TaskWatcherInline,
        TaskDependencyInline,
    ]

    # ------------------------------------------------------------
    # ACTION: Recompute selected tasks
    # ------------------------------------------------------------
    @admin.action(description="Recompute selected Tasks")
    def recompute_selected_tasks(self, request, queryset):
        from performance.services import TaskPolicyEngine

        with transaction.atomic():
            for task in queryset:
                TaskPolicyEngine.apply(task)
                task.save(update_fields=["percent_complete"])

        messages.success(request, "Task progress and SLA recalculated successfully.")

# -------- Assignments/Participants --------
@admin.register(ObjectiveDepartmentAssignment)
class ObjectiveDepartmentAssignmentAdmin(AppAdmin):
    list_display = ("id","objective","department","include_children","created_at","updated_at","created_by","updated_by")
    list_filter  = ("objective","include_children","created_at","updated_at")
    search_fields = ("objective__title","department__name")
    ordering = ("-id",)
    if USE_AUTOCOMPLETE: autocomplete_fields = ["objective","department"]
    else:                 raw_id_fields = ["objective","department"]
    readonly_fields = ("created_at","updated_at","created_by","updated_by")

@admin.register(ObjectiveEmployeeAssignment)
class ObjectiveEmployeeAssignmentAdmin(AppAdmin):
    list_display = ("id","objective","employee","created_at","updated_at","created_by","updated_by")
    list_filter  = ("objective","created_at","updated_at")
    search_fields = ("objective__title","employee__name")
    ordering = ("-id",)
    if USE_AUTOCOMPLETE: autocomplete_fields = ["objective","employee"]
    else:                 raw_id_fields = ["objective","employee"]
    readonly_fields = ("created_at","updated_at","created_by","updated_by")

@admin.register(ObjectiveParticipant)
class ObjectiveParticipantAdmin(AppAdmin):
    list_display = (
        "id",
        "objective",
        "employee",
        "created_at",
        "updated_at",
    )

    list_filter = (
        "objective",
        "employee",
        "created_at",
        "updated_at",
    )

    search_fields = (
        "objective__title",
        "objective__code",
        "employee__name",
        "employee__employee_id",
    )

    ordering = ("-id",)

    if USE_AUTOCOMPLETE:
        autocomplete_fields = ["objective", "employee"]
    else:
        raw_id_fields = ["objective", "employee"]

    # Allow add/change/delete
    def has_add_permission(self, request):
        return True

    def has_change_permission(self, request, obj=None):
        return True

    def has_delete_permission(self, request, obj=None):
        return True



@admin.register(EmployeeObjectiveScore)
class EmployeeObjectiveScoreAdmin(AppAdmin):
    list_display = ("objective", "employee", "contribution_pct", "tasks_progress_pct", "kpi_score_pct", "final_score_pct", "created_at")
    list_filter = ("objective", "employee")
    search_fields = ("objective__title", "employee__name")
    ordering = ("-final_score_pct",)


@admin.register(EmployeeObjectiveScoringPolicy)
class EmployeeObjectiveScoringPolicyAdmin(AppAdmin):
    list_display = (
        "company",
        "name",
        "code",
        "active",
        "tasks_weight_pct",
        "kpi_weight_pct",
        "timeliness_weight_pct",
        "efficiency_weight_pct",
        "quality_weight_pct",
        "created_at",
        "updated_at",
    )
    list_filter = ("company", "active")
    search_fields = ("name", "code")
    ordering = ("company", "name")
    readonly_fields = ("created_at", "updated_at")

    if USE_AUTOCOMPLETE:
        autocomplete_fields = ["company"]
    else:
        raw_id_fields = ["company"]

# -------- Templates / Parameters / Evaluations / Results --------

@admin.register(EvaluationType)
class EvaluationTypeAdmin(AppAdmin):
    list_display = (
        "id",
        "company",
        "name",
        "code",
        "sequence",
        "frequency_label",
        "active",
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
    )
    list_filter = ("company", "active", "created_at", "updated_at")
    search_fields = ("name", "code", "description")
    ordering = ("company", "sequence", "name")

    if USE_AUTOCOMPLETE:
        autocomplete_fields = ["company"]
    else:
        raw_id_fields = ["company"]

    readonly_fields = ("created_at", "updated_at", "created_by", "updated_by")

@admin.register(EvaluationApprovalStep)
class EvaluationApprovalStepAdmin(AppAdmin):
    list_display = (
        "id",
        "company",
        "evaluation_type",
        "name",
        "approver_kind",
        "manager_level",
        "approver_employee",
        "approver_group",
        "sequence",
        "active",
        "created_at",
        "updated_at",
    )
    list_filter = (
        "company",
        "evaluation_type",
        "approver_kind",
        "active",
        "created_at",
        "updated_at",
    )
    search_fields = ("name", "code", "evaluation_type__name")
    ordering = ("evaluation_type", "sequence", "id")

    if USE_AUTOCOMPLETE:
        autocomplete_fields = ["company", "evaluation_type", "approver_employee", "approver_group"]
    else:
        raw_id_fields = ["company", "evaluation_type", "approver_employee", "approver_group"]

    readonly_fields = ("created_at", "updated_at", "created_by", "updated_by")


@admin.register(EvaluationTemplate)
class EvaluationTemplateAdmin(AppAdmin):
    list_display = ("id","company","evaluation_type","name","active","created_at","updated_at","created_by","updated_by")
    list_filter  = ("company","evaluation_type","active","created_at","updated_at")
    search_fields = ("name","description")
    ordering = ("company","name")
    if USE_AUTOCOMPLETE:
        autocomplete_fields = ["company", "evaluation_type"]
    else:
        raw_id_fields = ["company", "evaluation_type"]
    readonly_fields = ("created_at","updated_at","created_by","updated_by")

    class EvaluationParameterInline(admin.TabularInline):
        model = EvaluationParameter
        extra = 0
        fields = ["name","code","weight_pct","source_kind",
                  "objective","kpi",
                  "external_model","external_field","external_aggregation","external_filter",
                  "manual_default_score_pct","min_score_pct","max_score_pct",
                  "created_at","updated_at","created_by","updated_by"]
        readonly_fields = ("created_at","updated_at","created_by","updated_by")
        if USE_AUTOCOMPLETE: autocomplete_fields = ["objective","kpi"]
        else:                 raw_id_fields = ["objective","kpi"]

    inlines = [EvaluationParameterInline]

    actions = [action_activate, action_deactivate]

@admin.register(EvaluationParameter)
class EvaluationParameterAdmin(AppAdmin):
    list_display = ("id","template","name","code","source_kind","weight_pct","objective","kpi",
                    "min_score_pct","max_score_pct","created_at","updated_at","created_by","updated_by")
    list_filter  = ("template","source_kind","created_at","updated_at")
    search_fields = ("name","code")
    ordering = ("template","name")
    if USE_AUTOCOMPLETE: autocomplete_fields = ["template","objective","kpi"]
    else:                 raw_id_fields = ["template","objective","kpi"]
    readonly_fields = ("created_at","updated_at","created_by","updated_by")


@admin.register(Evaluation)
class EvaluationAdmin(AppAdmin):
    list_display = (
        "id",
        "company",
        "employee",
        "evaluator",
        "date_start",
        "date_end",
        "template",
        "evaluation_type",
        "final_score_pct",        # نتيجة النظام الآلية
        "calibrated_score_pct",   # نتيجة المعايرة (إن وجدت)
        "effective_score",        # الدرجة المعتمدة فعلياً (final أو calibrated)
        "overall_rating",
        "active",
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
    )
    list_filter = (
        "company",
        "template",
        "evaluation_type",
        "date_start",
        "date_end",
        "active",
        "created_at",
        "updated_at",
    )
    search_fields = (
        "employee__name",
        "evaluator__name",
        "overall_rating",
        "calibration_reason",   # بدلاً من calibration_notes
    )
    ordering = ("-date_end", "-id")
    if USE_AUTOCOMPLETE:
        autocomplete_fields = ["company", "employee", "evaluator", "template", "evaluation_type"]
    else:
        raw_id_fields = ["company", "employee", "evaluator", "template", "evaluation_type"]

    readonly_fields = (
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
        # نجعل حقول المعايرة للقراءة فقط لأن تعديلها يتم عبر EvaluationCalibration
        "final_score_pct",
        "calibrated_score_pct",
        "calibration_reason",
        "calibration_applied_at",
        "calibration_applied_by",
    )

    class EvaluationParameterResultInline(admin.TabularInline):
        model = EvaluationParameterResult
        extra = 0
        fields = [
            "parameter",
            "raw_value_number",
            "raw_value_json",
            "score_pct",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]
        readonly_fields = ("created_at", "updated_at", "created_by", "updated_by")
        if USE_AUTOCOMPLETE:
            autocomplete_fields = ["parameter"]
        else:
            raw_id_fields = ["parameter"]

    inlines = [EvaluationParameterResultInline]

    actions = ["recompute_evaluations", action_activate, action_deactivate]

    @admin.display(description="Effective Score")
    def effective_score(self, obj):
        """
        الدرجة المعتمدة فعلياً في التقارير:
          - إن كانت calibrated_score_pct موجودة تُستخدم
          - وإلا تُستخدم final_score_pct
        """
        return obj.calibrated_score_pct if obj.calibrated_score_pct is not None else obj.final_score_pct

    @admin.action(description="Recompute selected evaluations (final score + results)")
    def recompute_evaluations(self, request, queryset):
        """
        يعيد احتساب نتائج الـ EvaluationParameterResult والـ final_score_pct
        بدون لمس أي حقول معايرة (calibrated_*).
        """
        with transaction.atomic():
            for ev in queryset:
                ev.recompute()
                # نحفظ فقط نتيجة النظام الآلية ولا نلمس حقول المعايرة
                ev.save(update_fields=["final_score_pct", "updated_at", "updated_by"])
        messages.success(request, "Evaluations recomputed successfully.")


@admin.register(EvaluationParameterResult)
class EvaluationParameterResultAdmin(AppAdmin):
    list_display = ("id","evaluation","parameter","score_pct","created_at","updated_at","created_by","updated_by")
    list_filter  = ("parameter__template","created_at","updated_at")
    search_fields = ("evaluation__employee__name","parameter__name")
    ordering = ("-id",)
    if USE_AUTOCOMPLETE: autocomplete_fields = ["evaluation","parameter"]
    else:                 raw_id_fields = ["evaluation","parameter"]
    readonly_fields = ("created_at","updated_at","created_by","updated_by")



@admin.register(DailyRatingFactor)
class DailyRatingFactorAdmin(AppAdmin):
    list_display = ("id", "company", "name", "weight_pct", "active", "created_at")
    list_filter  = ("company", "active")
    search_fields = ("name", "description")
    ordering = ("company", "name")
    if USE_AUTOCOMPLETE:
        autocomplete_fields = ["company"]


class DailyRatingItemInline(admin.TabularInline):
    model = DailyRatingItem
    extra = 0
    fields = ["factor", "score_pct", "comment"]
    if USE_AUTOCOMPLETE:
        autocomplete_fields = ["factor"]


@admin.register(DailyRating)
class DailyRatingAdmin(AppAdmin):
    list_display = ("id", "company", "employee", "rated_by", "date", "overall_score_pct", "created_at")
    list_filter  = ("company", "date")
    search_fields = ("employee__name",)
    ordering = ("-date",)
    if USE_AUTOCOMPLETE:
        autocomplete_fields = ["company", "employee", "rated_by"]

    inlines = [DailyRatingItemInline]


@admin.register(PerformanceExceptionType)
class PerformanceExceptionTypeAdmin(AppAdmin):
    list_display = ("id", "company", "name", "multiplier", "is_positive", "max_impact_pct", "active")
    list_filter  = ("company", "active")
    search_fields = ("name",)
    ordering = ("company", "name")
    if USE_AUTOCOMPLETE: autocomplete_fields = ["company"]


@admin.register(PerformanceException)
class PerformanceExceptionAdmin(AppAdmin):
    list_display = ("id", "company", "employee", "type", "date_start", "date_end", "impact_pct")
    list_filter  = ("company", "type", "date_start")
    search_fields = ("employee__name",)
    ordering = ("-date_start",)
    if USE_AUTOCOMPLETE: autocomplete_fields = ["company", "employee", "type"]


@admin.register(EvaluationExceptionAdjustment)
class EvaluationExceptionAdjustmentAdmin(AppAdmin):
    list_display = ("id", "evaluation", "exception", "adjustment_pct", "created_at")
    list_filter  = ("evaluation",)
    search_fields = ("evaluation__employee__name",)
    ordering = ("-id",)


@admin.register(QualityIncident)
class QualityIncidentAdmin(AppAdmin):
    list_display = ("id", "company", "employee", "severity", "impact_score_pct", "date")
    list_filter = ("company", "severity", "date")
    search_fields = ("employee__name", "description")
    ordering = ("-date",)
    if USE_AUTOCOMPLETE:
        autocomplete_fields = ["company", "employee"]

@admin.register(EvaluationFeedback)
class EvaluationFeedbackAdmin(AppAdmin):
    list_display = ("id", "company", "evaluation", "role", "overall_score_pct", "from_employee", "created_at")
    list_filter = ("company", "role")
    search_fields = ("evaluation__employee__name", "from_employee__name", "comment")
    ordering = ("-created_at",)
    if USE_AUTOCOMPLETE:
        autocomplete_fields = ["company", "evaluation", "from_employee"]


@admin.register(EvaluationCalibration)
class EvaluationCalibrationAdmin(AppAdmin):
    list_display = (
        "id",
        "company",
        "evaluation",
        "old_score_pct",
        "new_score_pct",
        "applied_by",
        "created_at",
    )
    list_filter = ("company",)
    search_fields = ("evaluation__employee__name", "reason")
    ordering = ("-created_at",)
    if USE_AUTOCOMPLETE:
        autocomplete_fields = ["company", "evaluation", "applied_by"]
