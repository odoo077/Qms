# -*- coding: utf-8 -*-
# هذا الملف يجمع جميع الفورمات داخل مجلد forms ليكون الاستيراد منظّمًا وسهلًا عبر باكج واحد

# مكسنات مشتركة (تنسيق Tailwind + تمرير الشركة لتقييد القوائم)
from .base import TailwindFormMixin, CompanyScopedFormMixin

# فورم الهدف + فورم سِت لأوزان KPI داخل الهدف
from .objective_form import ObjectiveForm, KPIWeightInlineFormSet

# فورم KPI
from .kpi_form import KPIForm

# فورم المهمة
from .task_form import TaskForm

# فورم قالب التقييم + فورم سِت لباراميترات القالب
from .evaluation_template_form import (
    EvaluationTemplateForm,
    EvaluationParameterInlineFormSet,
)

# فورم باراميتر التقييم
from .evaluation_parameter_form import EvaluationParameterForm

# فورم التقييم + فورم سِت لنتائج باراميترات التقييم
from .evaluation_form import (
    EvaluationForm,
    EvaluationParameterResultInlineFormSet,
)

# فورمات تعيينات الهدف (قسم/موظف)
from .objective_assignment_department_form import ObjectiveDepartmentAssignmentForm
from .objective_assignment_employee_form import ObjectiveEmployeeAssignmentForm


# تصدير الأسماء العامة للاستيراد المختصر من الخارج
__all__ = [
    # Mixins
    "TailwindFormMixin",
    "CompanyScopedFormMixin",

    # Objective + KPI inline weights
    "ObjectiveForm",
    "KPIWeightInlineFormSet",

    # KPI
    "KPIForm",

    # Task
    "TaskForm",

    # Evaluation Template + inline parameters
    "EvaluationTemplateForm",
    "EvaluationParameterInlineFormSet",

    # Evaluation Parameter
    "EvaluationParameterForm",

    # Evaluation + inline parameter results
    "EvaluationForm",
    "EvaluationParameterResultInlineFormSet",

    # Objective assignments
    "ObjectiveDepartmentAssignmentForm",
    "ObjectiveEmployeeAssignmentForm",
]
