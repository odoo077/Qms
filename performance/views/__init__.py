# -*- coding: utf-8 -*-
# هذا الملف يسهّل الاستيراد من حزمة views ويُظهر الواجهات المتاحة كواجهة عامة

from .mixins import (
    LoginRequired,
    CompanyScopedQuerysetMixin,
    UserStampedSaveMixin,
    ObjectPermissionRequiredMixin,
)

from .objectives import (
    ObjectiveListView,
    ObjectiveDetailView,
    ObjectiveCreateView,
    ObjectiveUpdateView,
    ObjectiveDeleteView,
)

from .kpis import (
    KPIListView,
    KPIDetailView,
    KPICreateView,
    KPIUpdateView,
    KPIDeleteView,
)

from .tasks import (
    TaskListView,
    TaskDetailView,
    TaskCreateView,
    TaskUpdateView,
    TaskDeleteView,
)

from .templates import (
    EvaluationTemplateListView,
    EvaluationTemplateDetailView,
    EvaluationTemplateCreateView,
    EvaluationTemplateUpdateView,
    EvaluationTemplateDeleteView,
)

from .parameters import (
    EvaluationParameterListView,
    EvaluationParameterDetailView,
    EvaluationParameterCreateView,
    EvaluationParameterUpdateView,
    EvaluationParameterDeleteView,
)

from .evaluations import (
    EvaluationListView,
    EvaluationDetailView,
    EvaluationCreateView,
    EvaluationUpdateView,
    EvaluationDeleteView,
)

__all__ = [
    # Mixins
    "LoginRequired",
    "CompanyScopedQuerysetMixin",
    "UserStampedSaveMixin",
    "ObjectPermissionRequiredMixin",

    # Objectives
    "ObjectiveListView",
    "ObjectiveDetailView",
    "ObjectiveCreateView",
    "ObjectiveUpdateView",
    "ObjectiveDeleteView",

    # KPIs
    "KPIListView",
    "KPIDetailView",
    "KPICreateView",
    "KPIUpdateView",
    "KPIDeleteView",

    # Tasks
    "TaskListView",
    "TaskDetailView",
    "TaskCreateView",
    "TaskUpdateView",
    "TaskDeleteView",

    # Evaluation Templates
    "EvaluationTemplateListView",
    "EvaluationTemplateDetailView",
    "EvaluationTemplateCreateView",
    "EvaluationTemplateUpdateView",
    "EvaluationTemplateDeleteView",

    # Evaluation Parameters
    "EvaluationParameterListView",
    "EvaluationParameterDetailView",
    "EvaluationParameterCreateView",
    "EvaluationParameterUpdateView",
    "EvaluationParameterDeleteView",

    # Evaluations
    "EvaluationListView",
    "EvaluationDetailView",
    "EvaluationCreateView",
    "EvaluationUpdateView",
    "EvaluationDeleteView",
]
