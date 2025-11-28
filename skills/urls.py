# skills/urls.py
from django.urls import path
from . import views

app_name = "skills"

urlpatterns = [
    # SkillType
    path("skilltypes/", views.SkillTypeListView.as_view(), name="skilltype_list"),
    path("skilltypes/new/", views.SkillTypeCreateView.as_view(), name="skilltype_create"),
    path("skilltypes/<int:pk>/edit/", views.SkillTypeUpdateView.as_view(), name="skilltype_update"),
    path("skilltypes/<int:pk>/delete/", views.SkillTypeDeleteView.as_view(), name="skilltype_delete"),

    # SkillLevel
    path("skilllevels/", views.SkillLevelListView.as_view(), name="skilllevel_list"),
    path("skilllevels/new/", views.SkillLevelCreateView.as_view(), name="skilllevel_create"),
    path("skilllevels/<int:pk>/edit/", views.SkillLevelUpdateView.as_view(), name="skilllevel_update"),
    path("skilllevels/<int:pk>/delete/", views.SkillLevelDeleteView.as_view(), name="skilllevel_delete"),

    # Skill
    path("skills/", views.SkillListView.as_view(), name="skill_list"),
    path("skills/new/", views.SkillCreateView.as_view(), name="skill_create"),
    path("skills/<int:pk>/edit/", views.SkillUpdateView.as_view(), name="skill_update"),
    path("skills/<int:pk>/delete/", views.SkillDeleteView.as_view(), name="skill_delete"),

    # EmployeeSkill
    path("employeeskills/", views.EmployeeSkillListView.as_view(), name="employeeskill_list"),
    path("employeeskills/new/", views.EmployeeSkillCreateView.as_view(), name="employeeskill_create"),
    path("employeeskills/<int:pk>/edit/", views.EmployeeSkillUpdateView.as_view(), name="employeeskill_update"),
    path("employeeskills/<int:pk>/delete/", views.EmployeeSkillDeleteView.as_view(), name="employeeskill_delete"),

    # ResumeLineType
    path("resumelinetypes/", views.ResumeLineTypeListView.as_view(), name="resumelinetype_list"),
    path("resumelinetypes/new/", views.ResumeLineTypeCreateView.as_view(), name="resumelinetype_create"),
    path("resumelinetypes/<int:pk>/edit/", views.ResumeLineTypeUpdateView.as_view(), name="resumelinetype_update"),
    path("resumelinetypes/<int:pk>/delete/", views.ResumeLineTypeDeleteView.as_view(), name="resumelinetype_delete"),

    # ResumeLine
    path("resumelines/", views.ResumeLineListView.as_view(), name="resumeline_list"),
    path("resumelines/new/", views.ResumeLineCreateView.as_view(), name="resumeline_create"),
    path("resumelines/<int:pk>/edit/", views.ResumeLineUpdateView.as_view(), name="resumeline_update"),
    path("resumelines/<int:pk>/delete/", views.ResumeLineDeleteView.as_view(), name="resumeline_delete"),
]
