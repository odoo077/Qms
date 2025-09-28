# skills/views/resume_line_type_views.py
from django.shortcuts import render, redirect, get_object_or_404
from skills.models.resume_line_type import HrResumeLineType
from skills.forms.resume_forms import ResumeLineTypeForm

def resume_line_type_list(request):
    types_ = HrResumeLineType.objects.order_by("sequence", "name")
    return render(request, "skills/resume_line_types/list.html", {"resume_line_types": types_})

def resume_line_type_create(request):
    form = ResumeLineTypeForm(request.POST or None)
    if form.is_valid():
        form.save()
        return redirect("skills:resume_line_type_list")
    return render(request, "skills/resume_line_types/form.html", {"form": form})

def resume_line_type_update(request, pk):
    rlt = get_object_or_404(HrResumeLineType, pk=pk)
    form = ResumeLineTypeForm(request.POST or None, instance=rlt)
    if form.is_valid():
        form.save()
        return redirect("skills:resume_line_type_list")
    return render(request, "skills/resume_line_types/form.html", {"form": form})

def resume_line_type_delete(request, pk):
    rlt = get_object_or_404(HrResumeLineType, pk=pk)
    rlt.delete()
    return redirect("skills:resume_line_type_list")
