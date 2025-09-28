from django.shortcuts import render, get_object_or_404, redirect
from skills.models import HrSkillType, HrSkillLevel, HrSkill
from skills.forms.skill_forms import SkillTypeForm, SkillLevelForm, SkillForm

def skilltype_list(request):
    skilltypes = HrSkillType.objects.all()
    return render(request, "skills/skill_types/list.html", {"skill_types": skilltypes})

def skilltype_create(request):
    if request.method == "POST":
        form = SkillTypeForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("skills:skilltype_list")
    else:
        form = SkillTypeForm()
    return render(request, "skills/skill_types/form.html", {"form": form})

def skilltype_update(request, pk):
    st = get_object_or_404(HrSkillType, pk=pk)
    form = SkillTypeForm(request.POST or None, instance=st)
    if form.is_valid():
        form.save()
        return redirect("skills:skill_type_list")
    return render(request, "skills/skill_types/form.html", {"form": form})

def skilltype_delete(request, pk):
    st = get_object_or_404(HrSkillType, pk=pk)
    st.delete()
    return redirect("skills:skill_type_list")


def skill_list(request):
    skills = HrSkill.objects.select_related("skill_type").all()
    return render(request, "skills/skills/list.html", {"skills": skills})

def skill_create(request):
    form = SkillForm(request.POST or None)
    if form.is_valid():
        form.save()
        return redirect("skills:skill_list")
    return render(request, "skills/skills/form.html", {"form": form})

def skill_update(request, pk):
    skill = get_object_or_404(HrSkill, pk=pk)
    form = SkillForm(request.POST or None, instance=skill)
    if form.is_valid():
        form.save()
        return redirect("skills:skill_list")
    return render(request, "skills/skills/form.html", {"form": form})

def skill_delete(request, pk):
    skill = get_object_or_404(HrSkill, pk=pk)
    skill.delete()
    return redirect("skills:skill_list")