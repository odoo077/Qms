# performance/admin.py
"""
لوحة الإدارة — مستثناة من صلاحيات الكائن عبر AppAdmin (مثل بقية التطبيقات).
"""

from django.contrib import admin, messages
from django.db import transaction
from base.admin_mixins import AppAdmin  # ✅ الاستثناء من صلاحيات الكائن
from base.admin import ObjectACLInline

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
    EvaluationCalibration, EmployeeObjectiveScoringPolicy,
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
        "priority", "estimated_minutes", "actual_minutes", "quality_score_pct", "active"
    ]
    if USE_AUTOCOMPLETE: autocomplete_fields = ["assignee","kpi"]
    else:                 raw_id_fields = ["assignee","kpi"]


# -------- Objective --------
@admin.register(Objective)
class ObjectiveAdmin(AppAdmin):
    list_display = ("id", "company", "code", "title", "parent", "hierarchy_level", "rollup_strategy", "date_start", "date_end", "status",
                    "target_kind", "target_department", "target_employee",
                    "weight_pct", "progress_pct", "score_pct", "active",
                    "created_at", "updated_at", "created_by", "updated_by")
    list_filter = ("company", "status", "target_kind", "active", "date_start", "date_end", "created_at", "updated_at")
    search_fields = ("code","title","description")
    ordering = ("-id",)
    if USE_AUTOCOMPLETE:
        autocomplete_fields = ["company", "reviewer","parent", "target_department", "target_employee"]
    else:
        raw_id_fields = ["company", "reviewer", "target_department", "target_employee"]

    readonly_fields = ("created_at","updated_at","created_by","updated_by")
    inlines = [ObjectACLInline, ObjectiveDepartmentAssignmentInline, ObjectiveEmployeeAssignmentInline, ObjectiveParticipantInline, KPIInline, TaskInline]

    actions = ["rebuild_participants","recompute_objectives",action_activate,action_deactivate]

    @admin.action(description="Rebuild participants for selected objectives")
    def rebuild_participants(self, request, queryset):
        with transaction.atomic():
            for obj in queryset: obj._rebuild_participants()
        messages.success(request, f"Rebuilt participants for {queryset.count()} objective(s).")

    @admin.action(description="Recompute progress/score for selected objectives")
    def recompute_objectives(self, request, queryset):
        with transaction.atomic():
            for obj in queryset:
                obj.recompute_progress_and_score()
                obj.save(update_fields=["progress_pct","score_pct"])
        messages.success(request, f"Recomputed {queryset.count()} objective(s).")


# -------- KPI --------
@admin.register(KPI)
class KPIAdmin(AppAdmin):
    list_display = ("id","company","objective","name","unit","higher_is_better","weight_pct",
                    "attainment_pct","score_pct","active","created_at","updated_at","created_by","updated_by")
    list_filter  = ("company","unit","higher_is_better","objective","active","created_at","updated_at")
    search_fields = ("name","description")
    ordering = ("-id",)
    if USE_AUTOCOMPLETE: autocomplete_fields = ["company","objective"]
    else:                 raw_id_fields = ["company","objective"]
    readonly_fields = ("created_at","updated_at","created_by","updated_by")
    actions = ["recompute_kpis", action_activate, action_deactivate]

    inlines = [ObjectACLInline]

    @admin.action(description="Recompute selected KPIs")
    def recompute_kpis(self, request, queryset):
        with transaction.atomic():
            for k in queryset:
                k.recompute()
                k.save(update_fields=["attainment_pct","score_pct"])
        messages.success(request, "KPI values recomputed.")


# -------- Task --------
@admin.register(Task)
class TaskAdmin(AppAdmin):
    list_display = (
        "id", "company", "objective", "title", "assignee", "status", "percent_complete",
        "due_date", "kpi",
        "task_kind", "priority", "estimated_minutes", "actual_minutes", "quality_score_pct",
        "active", "created_at", "updated_at", "created_by", "updated_by"
    )
    list_filter  = ("company","status","due_date","task_kind","priority","objective","active","created_at","updated_at")
    search_fields = ("title","description")
    ordering = ("-id",)
    if USE_AUTOCOMPLETE: autocomplete_fields = ["company","objective","assignee","kpi"]
    else:                 raw_id_fields = ["company","objective","assignee","kpi"]
    readonly_fields = ("created_at","updated_at","created_by","updated_by")
    actions = [action_activate, action_deactivate]

    inlines = [ObjectACLInline]


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
    list_display = ("id","objective","employee","created_at","updated_at")
    list_filter  = ("objective","created_at","updated_at")
    search_fields = ("objective__title","employee__name")
    ordering = ("-id",)
    if USE_AUTOCOMPLETE: autocomplete_fields = ["objective","employee"]
    else:                 raw_id_fields = ["objective","employee"]
    readonly_fields = ("created_at","updated_at")
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False


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
    list_display = ("id","company","name","active","created_at","updated_at","created_by","updated_by")
    list_filter  = ("company","active","created_at","updated_at")
    search_fields = ("name","description")
    ordering = ("company","name")
    if USE_AUTOCOMPLETE: autocomplete_fields = ["company"]
    else:                 raw_id_fields = ["company"]
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

    inlines = [ObjectACLInline, EvaluationParameterInline]

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

    inlines = [ObjectACLInline]

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

    inlines = [ObjectACLInline, EvaluationParameterResultInline]

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

    inlines = [ObjectACLInline]



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
