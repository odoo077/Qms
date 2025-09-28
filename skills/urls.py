# skills/urls.py
from django.urls import path

from skills.views import skill_views
from skills.views import skill_level_views
from skills.views import employee_skill_views
from skills.views import resume_views
from skills.views import resume_line_type_views

app_name = "skills"

urlpatterns = [
    # Skill Types
    path("skill-types/",                 skill_views.skilltype_list,   name="skill_type_list"),
    path("skill-types/add/",             skill_views.skilltype_create, name="skill_type_create"),
    path("skill-types/<int:pk>/edit/",   skill_views.skilltype_update, name="skill_type_update"),
    path("skill-types/<int:pk>/delete/", skill_views.skilltype_delete, name="skill_type_delete"),

    # Skill Levels
    path("skill-levels/",                 skill_level_views.skilllevel_list,   name="skill_level_list"),
    path("skill-levels/add/",             skill_level_views.skilllevel_create, name="skill_level_create"),
    path("skill-levels/<int:pk>/edit/",   skill_level_views.skilllevel_update, name="skill_level_update"),
    path("skill-levels/<int:pk>/delete/", skill_level_views.skilllevel_delete, name="skill_level_delete"),

    # Skills
    path("skills/",                 skill_views.skill_list,   name="skill_list"),
    path("skills/add/",             skill_views.skill_create, name="skill_create"),
    path("skills/<int:pk>/edit/",   skill_views.skill_update, name="skill_update"),
    path("skills/<int:pk>/delete/", skill_views.skill_delete, name="skill_delete"),

    # Employee Skills
    path("employee-skills/",                 employee_skill_views.employee_skill_list,   name="employee_skill_list"),
    path("employee-skills/add/",             employee_skill_views.employee_skill_create, name="employee_skill_create"),
    path("employee-skills/<int:pk>/edit/",   employee_skill_views.employee_skill_update, name="employee_skill_update"),
    path("employee-skills/<int:pk>/delete/", employee_skill_views.employee_skill_delete, name="employee_skill_delete"),

    # Resume Lines
    path("resume-lines/",                 resume_views.resume_line_list,   name="resume_line_list"),
    path("resume-lines/add/",             resume_views.resume_line_create, name="resume_line_create"),
    path("resume-lines/<int:pk>/edit/",   resume_views.resume_line_update, name="resume_line_update"),
    path("resume-lines/<int:pk>/delete/", resume_views.resume_line_delete, name="resume_line_delete"),

    # Resume Line Types
    path("resume-line-types/",                 resume_line_type_views.resume_line_type_list,   name="resume_line_type_list"),
    path("resume-line-types/add/",             resume_line_type_views.resume_line_type_create, name="resume_line_type_create"),
    path("resume-line-types/<int:pk>/edit/",   resume_line_type_views.resume_line_type_update, name="resume_line_type_update"),
    path("resume-line-types/<int:pk>/delete/", resume_line_type_views.resume_line_type_delete, name="resume_line_type_delete"),
]
