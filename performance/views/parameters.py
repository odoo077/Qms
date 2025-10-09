# -*- coding: utf-8 -*-
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView

from .mixins import LoginRequired, CompanyScopedQuerysetMixin, UserStampedSaveMixin, ObjectPermissionRequiredMixin
from ..models.evaluation_parameter import EvaluationParameter
from ..forms import EvaluationParameterForm


class EvaluationParameterListView(LoginRequired, CompanyScopedQuerysetMixin, ListView):
    """قائمة باراميترات التقييم مع بحث بسيط"""
    model = EvaluationParameter
    template_name = "performance/evaluation_parameter_list.html"
    paginate_by = 20
    ordering = "template__name"

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(name__icontains=q) | qs.filter(code__icontains=q)
        return qs


class EvaluationParameterDetailView(LoginRequired, CompanyScopedQuerysetMixin, ObjectPermissionRequiredMixin, DetailView):
    """عرض تفصيلي لباراميتر تقييم مع صلاحيات كائن"""
    model = EvaluationParameter
    template_name = "performance/evaluation_parameter_detail.html"
    required_perms = ["performance.view_evaluationparameter"]

    def get_permission_object(self):
        return self.get_object()


class EvaluationParameterCreateView(LoginRequired, CompanyScopedQuerysetMixin, UserStampedSaveMixin, CreateView):
    """إنشاء باراميتر تقييم باستخدام الفورم المخصص"""
    model = EvaluationParameter
    form_class = EvaluationParameterForm
    template_name = "performance/evaluation_parameter_form.html"
    success_url = reverse_lazy("performance:evaluation_parameter_list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # قد لا تحتاج لتمرير الشركة هنا لأن الشركة تُستمد من القالب/العلاقات
        kwargs["company"] = getattr(self.request.user, "company", None) or getattr(self.request.user, "company_id", None)
        return kwargs


class EvaluationParameterUpdateView(LoginRequired, CompanyScopedQuerysetMixin, UserStampedSaveMixin, ObjectPermissionRequiredMixin, UpdateView):
    """تعديل باراميتر تقييم باستخدام الفورم المخصص + صلاحيات كائن"""
    model = EvaluationParameter
    form_class = EvaluationParameterForm
    template_name = "performance/evaluation_parameter_form.html"
    required_perms = ["performance.change_evaluationparameter"]
    success_url = reverse_lazy("performance:evaluation_parameter_list")

    def get_permission_object(self):
        return self.get_object()

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["company"] = getattr(self.request.user, "company", None) or getattr(self.request.user, "company_id", None)
        return kwargs


class EvaluationParameterDeleteView(LoginRequired, CompanyScopedQuerysetMixin, ObjectPermissionRequiredMixin, DeleteView):
    """حذف باراميتر تقييم مع صلاحيات كائن"""
    model = EvaluationParameter
    template_name = "performance/confirm_delete.html"
    success_url = reverse_lazy("performance:evaluation_parameter_list")
    required_perms = ["performance.delete_evaluationparameter"]

    def get_permission_object(self):
        return self.get_object()
