# -*- coding: utf-8 -*-
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView

from .mixins import LoginRequired, CompanyScopedQuerysetMixin, UserStampedSaveMixin, ObjectPermissionRequiredMixin
from ..models.task import Task
from ..forms import TaskForm


class TaskListView(LoginRequired, CompanyScopedQuerysetMixin, ListView):
    """قائمة المهام مع بحث وتصفية حالة"""
    model = Task
    template_name = "performance/task_list.html"
    paginate_by = 20
    ordering = "-id"

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(title__icontains=q) | qs.filter(description__icontains=q)
        status = self.request.GET.get("status")
        if status:
            qs = qs.filter(status=status)
        return qs


class TaskDetailView(LoginRequired, CompanyScopedQuerysetMixin, ObjectPermissionRequiredMixin, DetailView):
    """عرض تفصيلي لمهمة مع صلاحيات كائن"""
    model = Task
    template_name = "performance/task_detail.html"
    required_perms = ["performance.view_task"]

    def get_permission_object(self):
        return self.get_object()


class TaskCreateView(LoginRequired, CompanyScopedQuerysetMixin, UserStampedSaveMixin, CreateView):
    """إنشاء مهمة باستخدام الفورم المخصص + تمرير الشركة"""
    model = Task
    form_class = TaskForm
    template_name = "performance/task_form.html"
    success_url = reverse_lazy("performance:task_list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["company"] = getattr(self.request.user, "company", None) or getattr(self.request.user, "company_id", None)
        return kwargs


class TaskUpdateView(LoginRequired, CompanyScopedQuerysetMixin, UserStampedSaveMixin, ObjectPermissionRequiredMixin, UpdateView):
    """تعديل مهمة باستخدام الفورم المخصص + صلاحيات كائن"""
    model = Task
    form_class = TaskForm
    template_name = "performance/task_form.html"
    required_perms = ["performance.change_task"]
    success_url = reverse_lazy("performance:task_list")

    def get_permission_object(self):
        return self.get_object()

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["company"] = getattr(self.request.user, "company", None) or getattr(self.request.user, "company_id", None)
        return kwargs


class TaskDeleteView(LoginRequired, CompanyScopedQuerysetMixin, ObjectPermissionRequiredMixin, DeleteView):
    """حذف مهمة مع صلاحيات كائن"""
    model = Task
    template_name = "performance/confirm_delete.html"
    success_url = reverse_lazy("performance:task_list")
    required_perms = ["performance.delete_task"]

    def get_permission_object(self):
        return self.get_object()
