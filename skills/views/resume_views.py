from django.shortcuts import render, redirect, get_object_or_404
from skills.models.resume_line import HrResumeLine
from skills.forms.resume_forms import ResumeLineForm

def resume_line_list(request):
    lines = HrResumeLine.objects.select_related("employee", "line_type").all()
    return render(request, "skills/resume_lines/list.html", {"resume_lines": lines})

def resume_line_create(request):
    form = ResumeLineForm(request.POST or None, request.FILES or None)
    if form.is_valid():
        form.save()
        return redirect("skills:resume_line_list")
    return render(request, "skills/resume_lines/form.html", {"form": form})

def resume_line_update(request, pk):
    line = get_object_or_404(HrResumeLine, pk=pk)
    form = ResumeLineForm(request.POST or None, request.FILES or None, instance=line)
    if form.is_valid():
        form.save()
        return redirect("skills:resume_line_list")
    return render(request, "skills/resume_lines/form.html", {"form": form})

def resume_line_delete(request, pk):
    line = get_object_or_404(HrResumeLine, pk=pk)
    line.delete()
    return redirect("skills:resume_line_list")
