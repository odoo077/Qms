# -*- coding: utf-8 -*-
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView

from .mixins import LoginRequired, CompanyScopedQuerysetMixin, UserStampedSaveMixin, ObjectPermissionRequiredMixin
from ..models.evaluation import Evaluation
from ..forms import EvaluationForm


class EvaluationListView(LoginRequired, CompanyScopedQuerysetMixin, ListView):
    """قائمة التقييمات مع بحث باسم الموظف/المقيّم"""
    model = Evaluation
    template_name = "performance/evaluation_list.html"
    paginate_by = 20
    ordering = "-date_end"

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(employee__name__icontains=q) | qs.filter(evaluator__name__icontains=q)
        return qs


class EvaluationDetailView(LoginRequired, CompanyScopedQuerysetMixin, ObjectPermissionRequiredMixin, DetailView):
    """عرض تفصيلي لتقييم مع صلاحيات كائن"""
    model = Evaluation
    template_name = "performance/evaluation_detail.html"
    required_perms = ["performance.view_evaluation"]

    def get_permission_object(self):
        return self.get_object()


class EvaluationCreateView(LoginRequired, CompanyScopedQuerysetMixin, UserStampedSaveMixin, CreateView):
    """إنشاء تقييم باستخدام الفورم المخصص + تمرير الشركة"""
    model = Evaluation
    form_class = EvaluationForm
    template_name = "performance/evaluation_form.html"
    success_url = reverse_lazy("performance:evaluation_list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["company"] = getattr(self.request.user, "company", None) or getattr(self.request.user, "company_id", None)
        return kwargs


class EvaluationUpdateView(LoginRequired, CompanyScopedQuerysetMixin, UserStampedSaveMixin, ObjectPermissionRequiredMixin, UpdateView):
    """تعديل تقييم باستخدام الفورم المخصص + صلاحيات كائن"""
    model = Evaluation
    form_class = EvaluationForm
    template_name = "performance/evaluation_form.html"
    required_perms = ["performance.change_evaluation"]
    success_url = reverse_lazy("performance:evaluation_list")

    def get_permission_object(self):
        return self.get_object()

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["company"] = getattr(self.request.user, "company", None) or getattr(self.request.user, "company_id", None)
        return kwargs


class EvaluationDeleteView(LoginRequired, CompanyScopedQuerysetMixin, ObjectPermissionRequiredMixin, DeleteView):
    """حذف تقييم مع صلاحيات كائن"""
    model = Evaluation
    template_name = "performance/confirm_delete.html"
    success_url = reverse_lazy("performance:evaluation_list")
    required_perms = ["performance.delete_evaluation"]

    def get_permission_object(self):
        return self.get_object()
