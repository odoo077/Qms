# -*- coding: utf-8 -*-
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView

# مكسنات الحماية والنطاق
from .mixins import LoginRequired, CompanyScopedQuerysetMixin, UserStampedSaveMixin, ObjectPermissionRequiredMixin
# الموديل
from ..models.objective import Objective
# الفورم المخصص
from ..forms import ObjectiveForm


class ObjectiveListView(LoginRequired, CompanyScopedQuerysetMixin, ListView):
    """قائمة الأهداف مع بحث بسيط وتقييد على الشركة"""
    model = Objective
    template_name = "performance/objective_list.html"
    paginate_by = 20
    ordering = "-id"

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(title__icontains=q) | qs.filter(code__icontains=q) | qs.filter(description__icontains=q)
        return qs


class ObjectiveDetailView(LoginRequired, CompanyScopedQuerysetMixin, ObjectPermissionRequiredMixin, DetailView):
    """عرض تفصيلي للهدف مع تحقّق صلاحيات كائن"""
    model = Objective
    template_name = "performance/objective_detail.html"
    required_perms = ["performance.view_objective"]

    def get_permission_object(self):
        return self.get_object()


class ObjectiveCreateView(LoginRequired, CompanyScopedQuerysetMixin, UserStampedSaveMixin, CreateView):
    """إنشاء هدف باستخدام الفورم المخصص وتمرير الشركة للفورم"""
    model = Objective
    form_class = ObjectiveForm
    template_name = "performance/objective_form.html"
    success_url = reverse_lazy("performance:objective_list")

    def get_form_kwargs(self):
        # تمرير company للفورم لتقييد القوائم
        kwargs = super().get_form_kwargs()
        kwargs["company"] = getattr(self.request.user, "company", None) or getattr(self.request.user, "company_id", None)
        return kwargs


class ObjectiveUpdateView(LoginRequired, CompanyScopedQuerysetMixin, UserStampedSaveMixin, ObjectPermissionRequiredMixin, UpdateView):
    """تعديل هدف باستخدام الفورم المخصص + صلاحيات كائن"""
    model = Objective
    form_class = ObjectiveForm
    template_name = "performance/objective_form.html"
    required_perms = ["performance.change_objective"]
    success_url = reverse_lazy("performance:objective_list")

    def get_permission_object(self):
        return self.get_object()

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["company"] = getattr(self.request.user, "company", None) or getattr(self.request.user, "company_id", None)
        return kwargs


class ObjectiveDeleteView(LoginRequired, CompanyScopedQuerysetMixin, ObjectPermissionRequiredMixin, DeleteView):
    """حذف هدف مع تحقّق صلاحيات كائن"""
    model = Objective
    template_name = "performance/confirm_delete.html"
    success_url = reverse_lazy("performance:objective_list")
    required_perms = ["performance.delete_objective"]

    def get_permission_object(self):
        return self.get_object()
