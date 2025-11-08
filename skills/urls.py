# skills/urls.py
from django.urls import path
from . import views

app_name = "skills"

urlpatterns = [
    # SkillType
    path("skilltypes/", views.SkillTypeListView.as_view(), name="skilltype_list"),
    path("skilltypes/new/", views.SkillTypeCreateView.as_view(), name="skilltype_create"),
    path("skilltypes/<int:pk>/edit/", views.SkillTypeUpdateView.as_view(), name="skilltype_edit"),

    # SkillLevel
    path("skilllevels/", views.SkillLevelListView.as_view(), name="skilllevel_list"),
    path("skilllevels/new/", views.SkillLevelCreateView.as_view(), name="skilllevel_create"),
    path("skilllevels/<int:pk>/edit/", views.SkillLevelUpdateView.as_view(), name="skilllevel_edit"),

    # Skill
    path("skills/", views.SkillListView.as_view(), name="skill_list"),
    path("skills/new/", views.SkillCreateView.as_view(), name="skill_create"),
    path("skills/<int:pk>/edit/", views.SkillUpdateView.as_view(), name="skill_edit"),

    # EmployeeSkill
    path("employeeskills/", views.EmployeeSkillListView.as_view(), name="employeeskill_list"),
    path("employeeskills/new/", views.EmployeeSkillCreateView.as_view(), name="employeeskill_create"),
    path("employeeskills/<int:pk>/edit/", views.EmployeeSkillUpdateView.as_view(), name="employeeskill_edit"),

    # ResumeLineType
    path("resumelinetypes/", views.ResumeLineTypeListView.as_view(), name="resumelinetype_list"),
    path("resumelinetypes/new/", views.ResumeLineTypeCreateView.as_view(), name="resumelinetype_create"),
    path("resumelinetypes/<int:pk>/edit/", views.ResumeLineTypeUpdateView.as_view(), name="resumelinetype_edit"),

    # ResumeLine
    path("resumelines/", views.ResumeLineListView.as_view(), name="resumeline_list"),
    path("resumelines/new/", views.ResumeLineCreateView.as_view(), name="resumeline_create"),
    path("resumelines/<int:pk>/edit/", views.ResumeLineUpdateView.as_view(), name="resumeline_edit"),
]
