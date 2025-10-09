# -*- coding: utf-8 -*-
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView

from .mixins import LoginRequired, CompanyScopedQuerysetMixin, UserStampedSaveMixin, ObjectPermissionRequiredMixin
from ..models.kpi import KPI
from ..forms import KPIForm


class KPIListView(LoginRequired, CompanyScopedQuerysetMixin, ListView):
    """قائمة مؤشرات KPI مع بحث بسيط وتقييد على الشركة"""
    model = KPI
    template_name = "performance/kpi_list.html"
    paginate_by = 20
    ordering = "-id"

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(name__icontains=q) | qs.filter(description__icontains=q)
        return qs


class KPIDetailView(LoginRequired, CompanyScopedQuerysetMixin, ObjectPermissionRequiredMixin, DetailView):
    """عرض تفصيلي لـ KPI مع صلاحيات كائن"""
    model = KPI
    template_name = "performance/kpi_detail.html"
    required_perms = ["performance.view_kpi"]

    def get_permission_object(self):
        return self.get_object()


class KPICreateView(LoginRequired, CompanyScopedQuerysetMixin, UserStampedSaveMixin, CreateView):
    """إنشاء KPI باستخدام الفورم المخصص + تمرير الشركة"""
    model = KPI
    form_class = KPIForm
    template_name = "performance/kpi_form.html"
    success_url = reverse_lazy("performance:kpi_list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["company"] = getattr(self.request.user, "company", None) or getattr(self.request.user, "company_id", None)
        return kwargs


class KPIUpdateView(LoginRequired, CompanyScopedQuerysetMixin, UserStampedSaveMixin, ObjectPermissionRequiredMixin, UpdateView):
    """تعديل KPI باستخدام الفورم المخصص + صلاحيات كائن"""
    model = KPI
    form_class = KPIForm
    template_name = "performance/kpi_form.html"
    required_perms = ["performance.change_kpi"]
    success_url = reverse_lazy("performance:kpi_list")

    def get_permission_object(self):
        return self.get_object()

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["company"] = getattr(self.request.user, "company", None) or getattr(self.request.user, "company_id", None)
        return kwargs


class KPIDeleteView(LoginRequired, CompanyScopedQuerysetMixin, ObjectPermissionRequiredMixin, DeleteView):
    """حذف KPI مع صلاحيات كائن"""
    model = KPI
    template_name = "performance/confirm_delete.html"
    success_url = reverse_lazy("performance:kpi_list")
    required_perms = ["performance.delete_kpi"]

    def get_permission_object(self):
        return self.get_object()
