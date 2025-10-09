from .base import TailwindModelForm
from .skill_type_form import SkillTypeForm
from .skill_level_form import SkillLevelForm
from .skill_form import SkillForm
from .employee_skill_form import EmployeeSkillForm, EmployeeSkillArchiveForm
from .resume_line_type_form import ResumeLineTypeForm
from .resume_line_form import ResumeLineForm

__all__ = [
    "TailwindModelForm",
    "SkillTypeForm",
    "SkillLevelForm",
    "SkillForm",
    "EmployeeSkillForm",
    "EmployeeSkillArchiveForm",
    "ResumeLineTypeForm",
    "ResumeLineForm",
]
