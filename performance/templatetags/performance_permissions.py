from django import template
from base.acl_service import has_perm

register = template.Library()

# -------------------------------------------------
# EvaluationParameter
# -------------------------------------------------
@register.simple_tag
def can_add_parameter(user):
    return user.has_perm("performance.add_evaluationparameter")


@register.simple_tag
def can_edit_parameter(user, obj):
    return has_perm(obj, user, "change")


@register.simple_tag
def can_delete_parameter(user, obj):
    return has_perm(obj, user, "delete")


# -------------------------------------------------
# EvaluationTemplate
# -------------------------------------------------
@register.simple_tag
def can_add_template(user):
    return user.has_perm("performance.add_evaluationtemplate")


@register.simple_tag
def can_edit_template(user, obj):
    return has_perm(obj, user, "change")


@register.simple_tag
def can_delete_template(user, obj):
    return has_perm(obj, user, "delete")


# -------------------------------------------------
# Evaluation
# -------------------------------------------------
@register.simple_tag
def can_add_evaluation(user):
    return user.has_perm("performance.add_evaluation")


@register.simple_tag
def can_edit_evaluation(user, obj):
    return has_perm(obj, user, "change")


@register.simple_tag
def can_delete_evaluation(user, obj):
    return has_perm(obj, user, "delete")


# -------------------------------------------------
# Objective
# -------------------------------------------------
@register.simple_tag
def can_add_objective(user):
    return user.has_perm("performance.add_objective")


@register.simple_tag
def can_edit_objective(user, obj):
    return has_perm(obj, user, "change")


@register.simple_tag
def can_delete_objective(user, obj):
    return has_perm(obj, user, "delete")


# -------------------------------------------------
# KPI
# -------------------------------------------------
@register.simple_tag
def can_add_kpi(user):
    return user.has_perm("performance.add_kpi")


@register.simple_tag
def can_edit_kpi(user, obj):
    return has_perm(obj, user, "change")


@register.simple_tag
def can_delete_kpi(user, obj):
    return has_perm(obj, user, "delete")


# -------------------------------------------------
# Task
# -------------------------------------------------
@register.simple_tag
def can_add_task(user):
    return user.has_perm("performance.add_task")


@register.simple_tag
def can_edit_task(user, obj):
    return has_perm(obj, user, "change")


@register.simple_tag
def can_delete_task(user, obj):
    return has_perm(obj, user, "delete")
