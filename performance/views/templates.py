# -*- coding: utf-8 -*-
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView

from .mixins import LoginRequired, CompanyScopedQuerysetMixin, UserStampedSaveMixin, ObjectPermissionRequiredMixin
from ..models.evaluation_template import EvaluationTemplate
from ..forms import EvaluationTemplateForm


class EvaluationTemplateListView(LoginRequired, CompanyScopedQuerysetMixin, ListView):
    """قائمة قوالب التقييم مع بحث بسيط"""
    model = EvaluationTemplate
    template_name = "performance/evaluation_template_list.html"
    paginate_by = 20
    ordering = "name"

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(name__icontains=q) | qs.filter(description__icontains=q)
        return qs


class EvaluationTemplateDetailView(LoginRequired, CompanyScopedQuerysetMixin, ObjectPermissionRequiredMixin, DetailView):
    """عرض تفصيلي لقالب تقييم مع صلاحيات كائن"""
    model = EvaluationTemplate
    template_name = "performance/evaluation_template_detail.html"
    required_perms = ["performance.view_evaluationtemplate"]

    def get_permission_object(self):
        return self.get_object()


class EvaluationTemplateCreateView(LoginRequired, CompanyScopedQuerysetMixin, UserStampedSaveMixin, CreateView):
    """إنشاء قالب تقييم باستخدام الفورم المخصص + تمرير الشركة"""
    model = EvaluationTemplate
    form_class = EvaluationTemplateForm
    template_name = "performance/evaluation_template_form.html"
    success_url = reverse_lazy("performance:evaluation_template_list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["company"] = getattr(self.request.user, "company", None) or getattr(self.request.user, "company_id", None)
        return kwargs


class EvaluationTemplateUpdateView(LoginRequired, CompanyScopedQuerysetMixin, UserStampedSaveMixin, ObjectPermissionRequiredMixin, UpdateView):
    """تعديل قالب تقييم باستخدام الفورم المخصص + صلاحيات كائن"""
    model = EvaluationTemplate
    form_class = EvaluationTemplateForm
    template_name = "performance/evaluation_template_form.html"
    required_perms = ["performance.change_evaluationtemplate"]
    success_url = reverse_lazy("performance:evaluation_template_list")

    def get_permission_object(self):
        return self.get_object()

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["company"] = getattr(self.request.user, "company", None) or getattr(self.request.user, "company_id", None)
        return kwargs


class EvaluationTemplateDeleteView(LoginRequired, CompanyScopedQuerysetMixin, ObjectPermissionRequiredMixin, DeleteView):
    """حذف قالب تقييم مع صلاحيات كائن"""
    model = EvaluationTemplate
    template_name = "performance/confirm_delete.html"
    success_url = reverse_lazy("performance:evaluation_template_list")
    required_perms = ["performance.delete_evaluationtemplate"]

    def get_permission_object(self):
        return self.get_object()
