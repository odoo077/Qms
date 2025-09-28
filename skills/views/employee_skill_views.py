from django.shortcuts import render, redirect, get_object_or_404
from skills.models.employee_skill import HrEmployeeSkill
from skills.forms.employee_skill_forms import EmployeeSkillForm

def employee_skill_list(request):
    employee_skills = HrEmployeeSkill.objects.select_related("employee", "skill", "skill_level").all()
    return render(request, "skills/employee_skills/list.html", {"employee_skills": employee_skills})

def employee_skill_create(request):
    form = EmployeeSkillForm(request.POST or None)
    if form.is_valid():
        form.save()
        return redirect("skills:employee_skill_list")
    return render(request, "skills/employee_skills/form.html", {"form": form})

def employee_skill_update(request, pk):
    es = get_object_or_404(HrEmployeeSkill, pk=pk)
    form = EmployeeSkillForm(request.POST or None, instance=es)
    if form.is_valid():
        form.save()
        return redirect("skills:employee_skill_list")
    return render(request, "skills/employee_skills/form.html", {"form": form})

def employee_skill_delete(request, pk):
    es = get_object_or_404(HrEmployeeSkill, pk=pk)
    es.delete()
    return redirect("skills:employee_skill_list")
