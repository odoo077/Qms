# performance/access.py
# ------------------------------------------------------------
# High-level business rules for Performance App
# ------------------------------------------------------------
# IMPORTANT:
#   - This file does NOT grant permissions.
#   - Does NOT interact with ACL (ObjectACL).
#   - Does NOT depend on fixed roles or group names.
#   - 100% based on actual models provided in performance/models.py
# ------------------------------------------------------------

from __future__ import annotations
from typing import Optional, Iterable

from django.contrib.auth import get_user_model

from hr.models import Employee, Department
from performance.models import (
    Objective,
    KPI,
    Task,
    Evaluation,
    EvaluationTemplate,
)
from base.access import (
    get_employee,
    is_manager_of,
    user_is_in_manager_chain,
    is_in_same_company,
    is_in_same_department,
    can_user_work_with_employee,
)

User = get_user_model()


# ============================================================
# 1) Objective business rules
# ============================================================

def can_view_objective(user: User, obj: Objective) -> bool:
    """
    High-level logic ONLY:
    A user can 'view' an Objective if:

    1) same company scope
    2) user is the reviewer
    3) user is participant (based on ObjectiveParticipant)
    4) user manages a department targeted by the objective
    5) user is part of a department targeted by the objective
    """
    if not user or not user.is_authenticated:
        return False

    if not is_in_same_company(user, obj.company_id):
        return False

    me = get_employee(user)
    if not me:
        return False

    # Reviewer
    if obj.reviewer_id == me.id:
        return True

    # Participant (via materialized participants)
    if obj.participants.filter(employee_id=me.id).exists():
        return True

    # Target: employee-level
    if obj.target_kind == "employee":
        if obj.target_employee_id == me.id:
            return True

    # Target: department-level
    if obj.target_kind == "department" and obj.target_department_id:
        # same dept
        if me.department_id == obj.target_department_id:
            return True
        # manager of target dept or its parents
        if user_is_in_manager_chain(user, obj.target_employee) if obj.target_employee else False:
            return True

    # Target: company-level → visible to all employees in same company
    if obj.target_kind == "company":
        return True

    return False


def can_edit_objective(user: User, obj: Objective) -> bool:
    """
    High-level business rule for editing an Objective.
    Editable if:

    - reviewer
    - manager of targeted employees
    - manager of targeted department(s)
    - direct/parent manager of participants
    """
    if not user or not user.is_authenticated:
        return False

    if not is_in_same_company(user, obj.company_id):
        return False

    me = get_employee(user)
    if not me:
        return False

    # Reviewer can edit
    if obj.reviewer_id == me.id:
        return True

    # Manager of target employee
    if obj.target_kind == "employee":
        if is_manager_of(user, obj.target_employee):
            return True

    # Manager of target department
    if obj.target_kind == "department":
        dept = obj.target_department
        # same dept manager
        if dept and dept.manager_id == me.id:
            return True
        # parent chain managers
        current = dept.parent if dept else None
        while current:
            if current.manager_id == me.id:
                return True
            current = current.parent

    return False


# ============================================================
# 2) Task business rules
# ============================================================

def can_view_task(user: User, task: Task) -> bool:
    """
    A Task is viewable if:
    - same company scope
    - user is the assignee
    - user is manager of the assignee
    - user is reviewer of the parent Objective
    - user participates in the Objective
    """
    if not user or not user.is_authenticated:
        return False

    if not is_in_same_company(user, task.company_id):
        return False

    me = get_employee(user)
    if not me:
        return False

    # assignee
    if task.assignee_id == me.id:
        return True

    # manager of assignee
    if task.assignee_id and is_manager_of(user, task.assignee):
        return True

    # reviewer of objective
    if task.objective.reviewer_id == me.id:
        return True

    # participant in objective
    if task.objective.participants.filter(employee_id=me.id).exists():
        return True

    return False


def can_edit_task(user: User, task: Task) -> bool:
    """
    Editable if:
    - user is the assignee
    - user is manager of assignee
    - user is reviewer of parent Objective
    """
    if not user or not user.is_authenticated:
        return False

    if not is_in_same_company(user, task.company_id):
        return False

    me = get_employee(user)
    if not me:
        return False

    if task.assignee_id == me.id:
        return True

    if task.assignee_id and is_manager_of(user, task.assignee):
        return True

    if task.objective.reviewer_id == me.id:
        return True

    return False


# ============================================================
# 3) KPI business rules
# ============================================================

def can_view_kpi(user: User, kpi: KPI) -> bool:
    """Viewable if user can view its Objective."""
    return can_view_objective(user, kpi.objective)


def can_edit_kpi(user: User, kpi: KPI) -> bool:
    """Editable if user can edit its Objective."""
    return can_edit_objective(user, kpi.objective)


# ============================================================
# 4) Evaluation Template
# ============================================================

def can_view_template(user: User, template: EvaluationTemplate) -> bool:
    """
    Template visible if:
    - same company
    - user is evaluator for some employee
    - user is in HR chain (manager chain for employees)
    """
    if not user or not user.is_authenticated:
        return False

    if not is_in_same_company(user, template.company_id):
        return False

    me = get_employee(user)
    if not me:
        return False

    # User is evaluator for any employee in the company
    if Evaluation.objects.filter(evaluator_id=me.id, company_id=template.company_id).exists():
        return True

    # Managers (any manager chain)
    # If user manages someone who has an evaluation with this template
    if Evaluation.objects.filter(template_id=template.id).exists():
        evals = Evaluation.objects.filter(template_id=template.id)
        for e in evals.select_related("employee"):
            if is_manager_of(user, e.employee) or user_is_in_manager_chain(user, e.employee):
                return True

    return False


def can_edit_template(user: User, template: EvaluationTemplate) -> bool:
    """
    Editable if user has any evaluation responsibilities linked with the template.
    """
    if not user or not user.is_authenticated:
        return False

    if not is_in_same_company(user, template.company_id):
        return False

    me = get_employee(user)
    if not me:
        return False

    # Reviewer-like logic: if user evaluates someone using this template
    if Evaluation.objects.filter(template_id=template.id, evaluator_id=me.id).exists():
        return True

    # Manager of employees evaluated under this template
    evals = Evaluation.objects.filter(template_id=template.id)
    for e in evals.select_related("employee"):
        if is_manager_of(user, e.employee):
            return True

    return False


# ============================================================
# 5) Evaluation business rules
# ============================================================

def can_view_evaluation(user: User, evaluation: Evaluation) -> bool:
    """
    An evaluation is viewable if:

    - same company
    - user is employee being evaluated
    - user is evaluator
    - user manages the employee
    - user is in manager chain above employee
    """
    if not user or not user.is_authenticated:
        return False

    if not is_in_same_company(user, evaluation.company_id):
        return False

    me = get_employee(user)
    if not me:
        return False

    # self
    if evaluation.employee_id == me.id:
        return True

    # evaluator
    if evaluation.evaluator_id == me.id:
        return True

    # manager
    if is_manager_of(user, evaluation.employee):
        return True

    # parent chain manager
    if user_is_in_manager_chain(user, evaluation.employee):
        return True

    return False


def can_edit_evaluation(user: User, evaluation: Evaluation) -> bool:
    """
    Editable if:
    - same company
    - user is evaluator
    - user manages the employee
    """
    if not user or not user.is_authenticated:
        return False

    if not is_in_same_company(user, evaluation.company_id):
        return False

    me = get_employee(user)
    if not me:
        return False

    if evaluation.evaluator_id == me.id:
        return True

    if is_manager_of(user, evaluation.employee):
        return True

    return False
