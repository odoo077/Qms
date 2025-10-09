# skills/urls.py
from django.urls import path

# Skill Types
from .views.skill_types import (
    SkillTypeListView, SkillTypeCreateView, SkillTypeDetailView,
    SkillTypeUpdateView, SkillTypeDeleteView,
)

# Skill Levels
from .views.skill_levels import (
    SkillLevelListView, SkillLevelCreateView, SkillLevelDetailView,
    SkillLevelUpdateView, SkillLevelDeleteView,
)

# Skills
from .views.skills import (
    SkillListView, SkillCreateView, SkillDetailView,
    SkillUpdateView, SkillDeleteView,
)

# Employee Skills
from .views.employee_skills import (
    EmployeeSkillListView, EmployeeSkillCreateView, EmployeeSkillDetailView,
    EmployeeSkillUpdateView, EmployeeSkillDeleteView,
)

# Resume Line Types
from .views.resume_line_types import (
    ResumeLineTypeListView, ResumeLineTypeCreateView, ResumeLineTypeDetailView,
    ResumeLineTypeUpdateView, ResumeLineTypeDeleteView,
)

# Resume Lines
from .views.resume_lines import (
    ResumeLineListView, ResumeLineCreateView, ResumeLineDetailView,
    ResumeLineUpdateView, ResumeLineDeleteView,
)

app_name = "skills"

urlpatterns = [
    # Skill Types
    path("types/", SkillTypeListView.as_view(), name="skill_type_list"),
    path("types/new/", SkillTypeCreateView.as_view(), name="skill_type_create"),
    path("types/<int:pk>/", SkillTypeDetailView.as_view(), name="skill_type_detail"),
    path("types/<int:pk>/edit/", SkillTypeUpdateView.as_view(), name="skill_type_update"),
    path("types/<int:pk>/delete/", SkillTypeDeleteView.as_view(), name="skill_type_delete"),

    # Skill Levels
    path("levels/", SkillLevelListView.as_view(), name="skill_level_list"),
    path("levels/new/", SkillLevelCreateView.as_view(), name="skill_level_create"),
    path("levels/<int:pk>/", SkillLevelDetailView.as_view(), name="skill_level_detail"),
    path("levels/<int:pk>/edit/", SkillLevelUpdateView.as_view(), name="skill_level_update"),
    path("levels/<int:pk>/delete/", SkillLevelDeleteView.as_view(), name="skill_level_delete"),

    # Skills
    path("skills/", SkillListView.as_view(), name="skill_list"),
    path("skills/new/", SkillCreateView.as_view(), name="skill_create"),
    path("skills/<int:pk>/", SkillDetailView.as_view(), name="skill_detail"),
    path("skills/<int:pk>/edit/", SkillUpdateView.as_view(), name="skill_update"),
    path("skills/<int:pk>/delete/", SkillDeleteView.as_view(), name="skill_delete"),

    # Employee Skills
    path("employee-skills/", EmployeeSkillListView.as_view(), name="employee_skill_list"),
    path("employee-skills/new/", EmployeeSkillCreateView.as_view(), name="employee_skill_create"),
    path("employee-skills/<int:pk>/", EmployeeSkillDetailView.as_view(), name="employee_skill_detail"),
    path("employee-skills/<int:pk>/edit/", EmployeeSkillUpdateView.as_view(), name="employee_skill_update"),
    path("employee-skills/<int:pk>/delete/", EmployeeSkillDeleteView.as_view(), name="employee_skill_delete"),

    # Resume Line Types
    path("resume-line-types/", ResumeLineTypeListView.as_view(), name="resume_line_type_list"),
    path("resume-line-types/new/", ResumeLineTypeCreateView.as_view(), name="resume_line_type_create"),
    path("resume-line-types/<int:pk>/", ResumeLineTypeDetailView.as_view(), name="resume_line_type_detail"),
    path("resume-line-types/<int:pk>/edit/", ResumeLineTypeUpdateView.as_view(), name="resume_line_type_update"),
    path("resume-line-types/<int:pk>/delete/", ResumeLineTypeDeleteView.as_view(), name="resume_line_type_delete"),

    # Resume Lines
    path("resume-lines/", ResumeLineListView.as_view(), name="resume_line_list"),
    path("resume-lines/new/", ResumeLineCreateView.as_view(), name="resume_line_create"),
    path("resume-lines/<int:pk>/", ResumeLineDetailView.as_view(), name="resume_line_detail"),
    path("resume-lines/<int:pk>/edit/", ResumeLineUpdateView.as_view(), name="resume_line_update"),
    path("resume-lines/<int:pk>/delete/", ResumeLineDeleteView.as_view(), name="resume_line_delete"),
]
