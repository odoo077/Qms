# skills/views/__init__.py
from .skill_types import (
    SkillTypeListView, SkillTypeCreateView, SkillTypeDetailView,
    SkillTypeUpdateView, SkillTypeDeleteView,
)
from .skill_levels import (
    SkillLevelListView, SkillLevelCreateView, SkillLevelDetailView,
    SkillLevelUpdateView, SkillLevelDeleteView,
)
from .skills import (
    SkillListView, SkillCreateView, SkillDetailView,
    SkillUpdateView, SkillDeleteView,
)
from .employee_skills import (
    EmployeeSkillListView, EmployeeSkillCreateView, EmployeeSkillDetailView,
    EmployeeSkillUpdateView, EmployeeSkillDeleteView,
)
from .resume_line_types import (
    ResumeLineTypeListView, ResumeLineTypeCreateView, ResumeLineTypeDetailView,
    ResumeLineTypeUpdateView, ResumeLineTypeDeleteView,
)
from .resume_lines import (
    ResumeLineListView, ResumeLineCreateView, ResumeLineDetailView,
    ResumeLineUpdateView, ResumeLineDeleteView,
)

__all__ = [
    # Skill Types
    "SkillTypeListView","SkillTypeCreateView","SkillTypeDetailView","SkillTypeUpdateView","SkillTypeDeleteView",
    # Skill Levels
    "SkillLevelListView","SkillLevelCreateView","SkillLevelDetailView","SkillLevelUpdateView","SkillLevelDeleteView",
    # Skills
    "SkillListView","SkillCreateView","SkillDetailView","SkillUpdateView","SkillDeleteView",
    # Employee Skills
    "EmployeeSkillListView","EmployeeSkillCreateView","EmployeeSkillDetailView","EmployeeSkillUpdateView","EmployeeSkillDeleteView",
    # Resume Line Types
    "ResumeLineTypeListView","ResumeLineTypeCreateView","ResumeLineTypeDetailView","ResumeLineTypeUpdateView","ResumeLineTypeDeleteView",
    # Resume Lines
    "ResumeLineListView","ResumeLineCreateView","ResumeLineDetailView","ResumeLineUpdateView","ResumeLineDeleteView",
]
