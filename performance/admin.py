# performance/admin.py
from django.contrib import admin, messages
from django.db import transaction

from performance.models import ObjectiveDepartmentAssignment, Task, ObjectiveEmployeeAssignment, ObjectiveParticipant, KPI, \
    Objective, EvaluationTemplate, EvaluationParameter, Evaluation, EvaluationParameterResult

# -----------------------------------------------------------------------------
# Global toggle: prefer autocomplete widgets, fall back to raw_id if needed
# -----------------------------------------------------------------------------
USE_AUTOCOMPLETE = True


# -----------------------------------------------------------------------------
# Shared Admin Actions
# -----------------------------------------------------------------------------
@admin.action(description="Activate selected records")
def action_activate(modeladmin, request, queryset):
    updated = queryset.update(active=True)
    messages.success(request, f"Activated {updated} record(s).")

@admin.action(description="Deactivate selected records")
def action_deactivate(modeladmin, request, queryset):
    updated = queryset.update(active=False)
    messages.success(request, f"Deactivated {updated} record(s).")


# -----------------------------------------------------------------------------
# Inlines (Objective)
# -----------------------------------------------------------------------------
class ObjectiveDepartmentAssignmentInline(admin.TabularInline):
    model = ObjectiveDepartmentAssignment
    extra = 0
    fields = ["department", "include_children"]
    if USE_AUTOCOMPLETE:
        autocomplete_fields = ["department"]
    else:
        raw_id_fields = ["department"]
    fk_name = "objective"


class ObjectiveEmployeeAssignmentInline(admin.TabularInline):
    model = ObjectiveEmployeeAssignment
    extra = 0
    fields = ["employee"]
    if USE_AUTOCOMPLETE:
        autocomplete_fields = ["employee"]
    else:
        raw_id_fields = ["employee"]
    fk_name = "objective"


class ObjectiveParticipantInline(admin.TabularInline):
    """
    Participants are materialized automatically; show them read-only.
    """
    model = ObjectiveParticipant
    extra = 0
    can_delete = False
    fields = ["employee"]
    readonly_fields = ["employee", "objective"]
    if USE_AUTOCOMPLETE:
        autocomplete_fields = ["employee"]
    else:
        raw_id_fields = ["employee"]

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class KPIInline(admin.TabularInline):
    model = KPI
    extra = 0
    fields = [
        "name", "unit", "higher_is_better",
        "target_value", "baseline_value", "current_value",
        "weight_pct", "attainment_pct", "score_pct", "active",
    ]
    readonly_fields = ["attainment_pct", "score_pct"]


class TaskInline(admin.TabularInline):
    model = Task
    extra = 0
    fields = [
        "title", "assignee", "status", "percent_complete", "due_date", "kpi", "active",
    ]
    if USE_AUTOCOMPLETE:
        autocomplete_fields = ["assignee", "kpi"]
    else:
        raw_id_fields = ["assignee", "kpi"]


# -----------------------------------------------------------------------------
# Objective Admin (has: active, created_at/updated_at, created_by/updated_by)
# -----------------------------------------------------------------------------
@admin.register(Objective)
class ObjectiveAdmin(admin.ModelAdmin):
    list_display = (
        "id", "company", "code", "title",
        "date_start", "date_end", "status",
        "weight_pct", "progress_pct", "score_pct",
        "active", "created_at", "updated_at", "created_by", "updated_by",
    )
    list_filter = ("company", "status", "active", "date_start", "date_end", "created_at", "updated_at")
    search_fields = ("code", "title", "description")
    ordering = ("-id",)

    if USE_AUTOCOMPLETE:
        autocomplete_fields = ["company", "reviewer"]
    else:
        raw_id_fields = ["company", "reviewer"]

    readonly_fields = ("created_at", "updated_at", "created_by", "updated_by")

    inlines = [
        ObjectiveDepartmentAssignmentInline,
        ObjectiveEmployeeAssignmentInline,
        ObjectiveParticipantInline,
        KPIInline,
        TaskInline,
    ]
    actions = ["rebuild_participants", "recompute_objectives", action_activate, action_deactivate]

    @admin.action(description="Rebuild participants for selected objectives")
    def rebuild_participants(self, request, queryset):
        count = 0
        with transaction.atomic():
            for obj in queryset:
                obj._rebuild_participants()
                count += 1
        messages.success(request, f"Rebuilt participants for {count} objective(s).")

    @admin.action(description="Recompute progress/score for selected objectives")
    def recompute_objectives(self, request, queryset):
        count = 0
        with transaction.atomic():
            for obj in queryset:
                obj.recompute_progress_and_score()
                obj.save(update_fields=["progress_pct", "score_pct"])
                count += 1
        messages.success(request, f"Recomputed {count} objective(s).")


# -----------------------------------------------------------------------------
# KPI Admin (has: active, created_/updated_ + by)
# -----------------------------------------------------------------------------
@admin.register(KPI)
class KPIAdmin(admin.ModelAdmin):
    list_display = (
        "id", "company", "objective", "name", "unit",
        "higher_is_better", "weight_pct", "attainment_pct", "score_pct",
        "active", "created_at", "updated_at", "created_by", "updated_by",
    )
    list_filter = ("company", "unit", "higher_is_better", "objective", "active", "created_at", "updated_at")
    search_fields = ("name", "description")
    ordering = ("-id",)
    if USE_AUTOCOMPLETE:
        autocomplete_fields = ["company", "objective"]
    else:
        raw_id_fields = ["company", "objective"]
    readonly_fields = ("created_at", "updated_at", "created_by", "updated_by")
    actions = ["recompute_kpis", action_activate, action_deactivate]

    @admin.action(description="Recompute selected KPIs")
    def recompute_kpis(self, request, queryset):
        with transaction.atomic():
            for k in queryset:
                k.recompute()
                k.save(update_fields=["attainment_pct", "score_pct"])
        messages.success(request, "KPI values recomputed.")


# -----------------------------------------------------------------------------
# Task Admin (has: active, created_/updated_ + by)
# -----------------------------------------------------------------------------
@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = (
        "id", "company", "objective", "title", "assignee",
        "status", "percent_complete", "due_date", "kpi",
        "active", "created_at", "updated_at", "created_by", "updated_by",
    )
    list_filter = ("company", "status", "due_date", "objective", "active", "created_at", "updated_at")
    search_fields = ("title", "description")
    ordering = ("-id",)
    if USE_AUTOCOMPLETE:
        autocomplete_fields = ["company", "objective", "assignee", "kpi"]
    else:
        raw_id_fields = ["company", "objective", "assignee", "kpi"]
    readonly_fields = ("created_at", "updated_at", "created_by", "updated_by")
    actions = [action_activate, action_deactivate]


# -----------------------------------------------------------------------------
# ObjectiveDepartmentAssignment Admin (no active; has created_/updated_ + by)
# -----------------------------------------------------------------------------
@admin.register(ObjectiveDepartmentAssignment)
class ObjectiveDepartmentAssignmentAdmin(admin.ModelAdmin):
    list_display = ("id", "objective", "department", "include_children",
                    "created_at", "updated_at", "created_by", "updated_by")
    list_filter = ("objective", "include_children", "created_at", "updated_at")
    search_fields = ("objective__title", "department__name")
    ordering = ("-id",)
    if USE_AUTOCOMPLETE:
        autocomplete_fields = ["objective", "department"]
    else:
        raw_id_fields = ["objective", "department"]
    readonly_fields = ("created_at", "updated_at", "created_by", "updated_by")


# -----------------------------------------------------------------------------
# ObjectiveEmployeeAssignment Admin (no active; has created_/updated_ + by)
# -----------------------------------------------------------------------------
@admin.register(ObjectiveEmployeeAssignment)
class ObjectiveEmployeeAssignmentAdmin(admin.ModelAdmin):
    list_display = ("id", "objective", "employee",
                    "created_at", "updated_at", "created_by", "updated_by")
    list_filter = ("objective", "created_at", "updated_at")
    search_fields = ("objective__title", "employee__name")
    ordering = ("-id",)
    if USE_AUTOCOMPLETE:
        autocomplete_fields = ["objective", "employee"]
    else:
        raw_id_fields = ["objective", "employee"]
    readonly_fields = ("created_at", "updated_at", "created_by", "updated_by")


# -----------------------------------------------------------------------------
# ObjectiveParticipant Admin (no active; no created_by/updated_by)
# -----------------------------------------------------------------------------
@admin.register(ObjectiveParticipant)
class ObjectiveParticipantAdmin(admin.ModelAdmin):
    list_display = ("id", "objective", "employee", "created_at", "updated_at")
    list_filter = ("objective", "created_at", "updated_at")
    search_fields = ("objective__title", "employee__name")
    ordering = ("-id",)
    if USE_AUTOCOMPLETE:
        autocomplete_fields = ["objective", "employee"]
    else:
        raw_id_fields = ["objective", "employee"]
    readonly_fields = ("created_at", "updated_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


# -----------------------------------------------------------------------------
# EvaluationTemplate Admin (has: active, created_/updated_ + by)
# -----------------------------------------------------------------------------
@admin.register(EvaluationTemplate)
class EvaluationTemplateAdmin(admin.ModelAdmin):
    list_display = ("id", "company", "name",
                    "active", "created_at", "updated_at", "created_by", "updated_by")
    list_filter = ("company", "active", "created_at", "updated_at")
    search_fields = ("name", "description")
    ordering = ("company", "name")
    if USE_AUTOCOMPLETE:
        autocomplete_fields = ["company"]
    else:
        raw_id_fields = ["company"]
    readonly_fields = ("created_at", "updated_at", "created_by", "updated_by")

    class EvaluationParameterInline(admin.TabularInline):
        model = EvaluationParameter
        extra = 0
        fields = [
            "name", "code", "weight_pct", "source_kind",
            "objective", "kpi",
            "external_model", "external_field", "external_aggregation", "external_filter",
            "manual_default_score_pct", "min_score_pct", "max_score_pct",
            "created_at", "updated_at", "created_by", "updated_by",
        ]
        readonly_fields = ("created_at", "updated_at", "created_by", "updated_by")
        if USE_AUTOCOMPLETE:
            autocomplete_fields = ["objective", "kpi"]
        else:
            raw_id_fields = ["objective", "kpi"]

    inlines = [EvaluationParameterInline]
    actions = [action_activate, action_deactivate]


# -----------------------------------------------------------------------------
# EvaluationParameter Admin (no active; has created_/updated_ + by)
# -----------------------------------------------------------------------------
@admin.register(EvaluationParameter)
class EvaluationParameterAdmin(admin.ModelAdmin):
    list_display = (
        "id", "template", "name", "code", "source_kind",
        "weight_pct", "objective", "kpi",
        "min_score_pct", "max_score_pct",
        "created_at", "updated_at", "created_by", "updated_by",
    )
    list_filter = ("template", "source_kind", "created_at", "updated_at")
    search_fields = ("name", "code")
    ordering = ("template", "name")
    if USE_AUTOCOMPLETE:
        autocomplete_fields = ["template", "objective", "kpi"]
    else:
        raw_id_fields = ["template", "objective", "kpi"]
    readonly_fields = ("created_at", "updated_at", "created_by", "updated_by")


# -----------------------------------------------------------------------------
# Evaluation Admin (has: active, created_/updated_ + by)
# -----------------------------------------------------------------------------
@admin.register(Evaluation)
class EvaluationAdmin(admin.ModelAdmin):
    list_display = (
        "id", "company", "employee", "evaluator",
        "date_start", "date_end", "template",
        "final_score_pct", "overall_rating",
        "active", "created_at", "updated_at", "created_by", "updated_by",
    )
    list_filter = ("company", "template", "date_start", "date_end", "active", "created_at", "updated_at")
    search_fields = ("employee__name", "evaluator__name", "overall_rating", "calibration_notes")
    ordering = ("-date_end", "-id")
    if USE_AUTOCOMPLETE:
        autocomplete_fields = ["company", "employee", "evaluator", "template"]
    else:
        raw_id_fields = ["company", "employee", "evaluator", "template"]
    readonly_fields = ("created_at", "updated_at", "created_by", "updated_by")

    class EvaluationParameterResultInline(admin.TabularInline):
        model = EvaluationParameterResult
        extra = 0
        fields = ["parameter", "raw_value_number", "raw_value_json", "score_pct",
                  "created_at", "updated_at", "created_by", "updated_by"]
        readonly_fields = ("created_at", "updated_at", "created_by", "updated_by")
        if USE_AUTOCOMPLETE:
            autocomplete_fields = ["parameter"]
        else:
            raw_id_fields = ["parameter"]

    inlines = [EvaluationParameterResultInline]
    actions = ["recompute_evaluations", action_activate, action_deactivate]

    @admin.action(description="Recompute selected evaluations (final score + results)")
    def recompute_evaluations(self, request, queryset):
        with transaction.atomic():
            for ev in queryset:
                ev.recompute()
                ev.save(update_fields=["final_score_pct"])
        messages.success(request, "Evaluations recomputed successfully.")


# -----------------------------------------------------------------------------
# EvaluationParameterResult Admin (no active; has created_/updated_ + by)
# -----------------------------------------------------------------------------
@admin.register(EvaluationParameterResult)
class EvaluationParameterResultAdmin(admin.ModelAdmin):
    list_display = ("id", "evaluation", "parameter", "score_pct",
                    "created_at", "updated_at", "created_by", "updated_by")
    list_filter = ("parameter__template", "created_at", "updated_at")
    search_fields = ("evaluation__employee__name", "parameter__name")
    ordering = ("-id",)
    if USE_AUTOCOMPLETE:
        autocomplete_fields = ["evaluation", "parameter"]
    else:
        raw_id_fields = ["evaluation", "parameter"]
    readonly_fields = ("created_at", "updated_at", "created_by", "updated_by")
