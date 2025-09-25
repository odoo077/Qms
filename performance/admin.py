from django.contrib import admin
from .models import (
    Objective, KPI, Task, Evaluation,
    ObjectiveDepartmentAssignment, ObjectiveEmployeeAssignment, ObjectiveParticipant,
    EvaluationTemplate, EvaluationParameter, EvaluationParameterResult
)


# ----- Inlines -----
class KPIInline(admin.TabularInline):
    model = KPI
    extra = 0
    fields = ("name", "unit", "target_value", "current_value", "weight_pct", "attainment_pct", "score_pct")
    readonly_fields = ("attainment_pct", "score_pct")
    autocomplete_fields = ("company",)


class TaskInline(admin.TabularInline):
    model = Task
    extra = 0
    fields = ("title", "assignee", "due_date", "status", "percent_complete")
    autocomplete_fields = ("assignee",)


class DeptAssignmentInline(admin.TabularInline):
    model = ObjectiveDepartmentAssignment
    extra = 0
    fields = ("department", "include_children")
    autocomplete_fields = ("department",)


class EmpAssignmentInline(admin.TabularInline):
    model = ObjectiveEmployeeAssignment
    extra = 0
    fields = ("employee",)
    autocomplete_fields = ("employee",)


class EvaluationParameterInline(admin.TabularInline):
    model = EvaluationParameter
    extra = 0
    fields = (
        "name", "code", "weight_pct", "source_kind",
        "objective", "kpi",
        "external_model", "external_field", "external_aggregation", "external_filter",
        "manual_default_score_pct", "min_score_pct", "max_score_pct",
    )
    autocomplete_fields = ("objective", "kpi")


class EvaluationParameterResultInline(admin.TabularInline):
    model = EvaluationParameterResult
    extra = 0
    fields = ("parameter", "raw_value_number", "raw_value_json", "score_pct")
    readonly_fields = ("parameter", "raw_value_number", "raw_value_json", "score_pct")
    can_delete = False
    show_change_link = False


# ----- Objective -----
@admin.register(Objective)
class ObjectiveAdmin(admin.ModelAdmin):
    list_display = ("title", "company", "status", "progress_pct", "score_pct", "weight_pct", "date_start", "date_end")
    list_filter = ("company", "status", ("date_start", admin.DateFieldListFilter), ("date_end", admin.DateFieldListFilter))
    search_fields = ("title", "description")
    inlines = (KPIInline, TaskInline, DeptAssignmentInline, EmpAssignmentInline)
    readonly_fields = ("progress_pct", "score_pct")


# ----- KPI -----
@admin.register(KPI)
class KPIAdmin(admin.ModelAdmin):
    list_display = ("name", "objective", "unit", "target_value", "current_value", "attainment_pct", "score_pct", "weight_pct")
    list_filter = ("unit", "objective__company")
    search_fields = ("name", "objective__title")
    readonly_fields = ("attainment_pct", "score_pct")
    autocomplete_fields = ("objective", "company")


# ----- Task -----
@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("title", "objective", "assignee", "status", "percent_complete", "due_date")
    list_filter = ("status", "objective__company", ("due_date", admin.DateFieldListFilter))
    search_fields = ("title", "objective__title", "assignee__name")
    autocomplete_fields = ("objective", "assignee", "company")


# ----- Templates -----
@admin.register(EvaluationTemplate)
class EvaluationTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "company", "active", "total_weight_pct")
    list_filter = ("company", "active")
    search_fields = ("name", "description")
    autocomplete_fields = ("company",)
    inlines = (EvaluationParameterInline,)


@admin.register(EvaluationParameter)
class EvaluationParameterAdmin(admin.ModelAdmin):
    list_display = ("name", "template", "weight_pct", "source_kind", "objective", "kpi")
    list_filter = ("template", "source_kind")
    search_fields = ("name", "code", "template__name")
    autocomplete_fields = ("template", "objective", "kpi")
    ordering = ("template", "name")


# ----- Evaluation -----
@admin.register(Evaluation)
class EvaluationAdmin(admin.ModelAdmin):
    list_display = ("employee", "company", "template", "date_start", "date_end", "final_score_pct", "overall_rating")
    list_filter = ("company", "template", ("date_start", admin.DateFieldListFilter), ("date_end", admin.DateFieldListFilter))
    search_fields = ("employee__name",)
    autocomplete_fields = ("employee", "evaluator", "company", "template")
    readonly_fields = ("final_score_pct",)
    inlines = (EvaluationParameterResultInline,)

    actions = ("recompute_scores",)

    @admin.action(description="Recompute scores for selected evaluations")
    def recompute_scores(self, request, queryset):
        for ev in queryset:
            ev.recompute()
            ev.save(update_fields=["final_score_pct"])


# ----- Assignments & Participants -----
@admin.register(ObjectiveDepartmentAssignment)
class ObjectiveDeptAssignmentAdmin(admin.ModelAdmin):
    list_display = ("objective", "department", "include_children")
    autocomplete_fields = ("objective", "department")


@admin.register(ObjectiveEmployeeAssignment)
class ObjectiveEmpAssignmentAdmin(admin.ModelAdmin):
    list_display = ("objective", "employee")
    autocomplete_fields = ("objective", "employee")


@admin.register(ObjectiveParticipant)
class ObjectiveParticipantAdmin(admin.ModelAdmin):
    list_display = ("objective", "employee")
    autocomplete_fields = ("objective", "employee")
