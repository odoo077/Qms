# -*- coding: utf-8 -*-
from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView

# مكسنات الحماية وإدارة الصلاحيات
from .mixins import LoginRequired, ObjectPermissionRequiredMixin, CompanyScopedQuerysetMixin, UserStampedSaveMixin

# الموديلات ذات الصلة
from ..models.objective import Objective
from ..models.objective_department_assignment import ObjectiveDepartmentAssignment

# الفورم المخصص
from ..forms import ObjectiveDepartmentAssignmentForm


class ObjectiveDepartmentAssignmentListView(LoginRequired, CompanyScopedQuerysetMixin, ListView):
    """
    قائمة تعيينات الأقسام لهدف معيّن:
    - يتم تمرير pk في الـ URL لتمثيل الـ Objective
    - يتم تقييد النتائج على الهدف المحدد + الشركة الحالية
    """
    model = ObjectiveDepartmentAssignment
    template_name = "performance/objective_department_assignment_list.html"
    paginate_by = 20
    ordering = "-id"

    def dispatch(self, request, *args, **kwargs):
        self.objective = get_object_or_404(Objective, pk=self.kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(objective=self.objective)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["objective"] = self.objective
        return ctx


class ObjectiveDepartmentAssignmentCreateView(
    LoginRequired, UserStampedSaveMixin, ObjectPermissionRequiredMixin, CreateView
):
    """
    إنشاء تعيين قسم لهدف:
    - حماية بصلاحية change_objective على الهدف
    - تمرير company للفورم لتقييد القوائم
    - ربط الهدف تلقائياً في initial
    """
    model = ObjectiveDepartmentAssignment
    form_class = ObjectiveDepartmentAssignmentForm
    template_name = "performance/objective_department_assignment_form.html"
    required_perms = ["performance.change_objective"]

    def get_permission_object(self):
        return get_object_or_404(Objective, pk=self.kwargs["pk"])

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # تمرير الشركة للفورم لتقييد القوائم
        kwargs["company"] = getattr(self.request.user, "company", None) or getattr(self.request.user, "company_id", None)
        # ضبط الهدف افتراضياً
        initial = kwargs.get("initial", {}) or {}
        initial.setdefault("objective", self.get_permission_object())
        kwargs["initial"] = initial
        return kwargs

    def form_valid(self, form):
        # ضمان ربط السجل بالهدف الصحيح (حتى لو تغيّر initial)
        form.instance.objective = self.get_permission_object()
        response = super().form_valid(form)
        messages.success(self.request, "Department assignment has been created successfully.")
        return response

    def get_success_url(self):
        return reverse_lazy("performance:objective_detail", kwargs={"pk": self.kwargs["pk"]})


class ObjectiveDepartmentAssignmentUpdateView(
    LoginRequired, UserStampedSaveMixin, ObjectPermissionRequiredMixin, UpdateView
):
    """
    تعديل تعيين قسم:
    - حماية بصلاحية change_objective على نفس الهدف
    """
    model = ObjectiveDepartmentAssignment
    form_class = ObjectiveDepartmentAssignmentForm
    template_name = "performance/objective_department_assignment_form.html"
    required_perms = ["performance.change_objective"]

    def get_object(self, queryset=None):
        # نتأكد أن السجل يخص الهدف المحدد في الـ URL
        obj = get_object_or_404(ObjectiveDepartmentAssignment, pk=self.kwargs["assignment_pk"])
        if obj.objective_id != int(self.kwargs["pk"]):
            # حماية إضافية من الوصول لسجل لا يخص الهدف
            raise get_object_or_404(ObjectiveDepartmentAssignment, pk=-1)  # 404
        return obj

    def get_permission_object(self):
        return get_object_or_404(Objective, pk=self.kwargs["pk"])

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["company"] = getattr(self.request.user, "company", None) or getattr(self.request.user, "company_id", None)
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Department assignment has been updated successfully.")
        return response

    def get_success_url(self):
        return reverse_lazy("performance:objective_detail", kwargs={"pk": self.kwargs["pk"]})


class ObjectiveDepartmentAssignmentDeleteView(LoginRequired, ObjectPermissionRequiredMixin, DeleteView):
    """
    حذف تعيين قسم:
    - حماية بصلاحية change_objective على الهدف
    """
    model = ObjectiveDepartmentAssignment
    template_name = "performance/confirm_delete.html"
    required_perms = ["performance.change_objective"]

    def get_object(self, queryset=None):
        obj = get_object_or_404(ObjectiveDepartmentAssignment, pk=self.kwargs["assignment_pk"])
        if obj.objective_id != int(self.kwargs["pk"]):
            raise get_object_or_404(ObjectiveDepartmentAssignment, pk=-1)
        return obj

    def get_permission_object(self):
        return get_object_or_404(Objective, pk=self.kwargs["pk"])

    @transaction.atomic
    def delete(self, request, *args, **kwargs):
        messages.success(self.request, "Department assignment has been deleted.")
        return super().delete(request, *args, **kwargs)

    def get_success_url(self):
        return reverse_lazy("performance:objective_detail", kwargs={"pk": self.kwargs["pk"]})
