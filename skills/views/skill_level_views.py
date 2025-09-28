# skills/views/skill_level_views.py
from django.shortcuts import render, redirect, get_object_or_404
from skills.models.skill_level import HrSkillLevel
from skills.forms.skill_forms import SkillLevelForm

def skilllevel_list(request):
    levels = HrSkillLevel.objects.select_related("skill_type").order_by("skill_type__sequence", "level_progress")
    return render(request, "skills/skill_levels/list.html", {"skill_levels": levels})

def skilllevel_create(request):
    form = SkillLevelForm(request.POST or None)
    if form.is_valid():
        form.save()
        return redirect("skills:skill_level_list")
    return render(request, "skills/skill_levels/form.html", {"form": form})

def skilllevel_update(request, pk):
    level = get_object_or_404(HrSkillLevel, pk=pk)
    form = SkillLevelForm(request.POST or None, instance=level)
    if form.is_valid():
        form.save()
        return redirect("skills:skill_level_list")
    return render(request, "skills/skill_levels/form.html", {"form": form})

def skilllevel_delete(request, pk):
    level = get_object_or_404(HrSkillLevel, pk=pk)
    level.delete()
    return redirect("skills:skill_level_list")
