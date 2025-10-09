# -*- coding: utf-8 -*-
from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import FormView, View
from django.http import HttpResponseRedirect

from .mixins import LoginRequired, ObjectPermissionRequiredMixin
from ..models.objective import Objective
from ..forms import ObjectiveEmployeeAssignmentForm

# (اختياري) إذا أردت زرًا مستقلاً لإعادة بناء المشاركين
# from ..forms.participants_maintenance_form import RebuildParticipantsForm


class ObjectiveEmployeeBulkAssignView(LoginRequired, ObjectPermissionRequiredMixin, FormView):
    """
    تعيين جماعي لموظفين على هدف محدد:
    - يحترم صلاحية change_objective على الهدف
    - يمرر company للفورم ويقيّد الخيارات
    - بعد النجاح يعرض عدد السجلات التي تمت إضافتها فعليًا
    """
    template_name = "performance/objective_assignment_bulk_form.html"
    form_class = ObjectiveEmployeeAssignmentForm
    required_perms = ["performance.change_objective"]

    def get_permission_object(self):
        return get_object_or_404(Objective, pk=self.kwargs["pk"])

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # تمرير الشركة للفورم
        kwargs["company"] = getattr(self.request.user, "company", None) or getattr(self.request.user, "company_id", None)

        # يمكنك هنا تمرير employees_qs مقيَّد مسبقًا حسب سياساتك (مثلاً موظفي الشركة فقط)
        # kwargs["employees_qs"] = Employee.objects.filter(company_id=...)
        return kwargs

    @transaction.atomic
    def form_valid(self, form):
        created = form.save()
        # (اختياري) إعادة بناء المشاركين مباشرة بعد الإضافة الجماعية
        # self.get_permission_object()._rebuild_participants()

        messages.success(self.request, f"{created} employee(s) have been assigned to the objective.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("performance:objective_detail", kwargs={"pk": self.kwargs["pk"]})


class ObjectiveRebuildParticipantsView(LoginRequired, ObjectPermissionRequiredMixin, View):
    """
    (اختياري) إجراء لإعادة بناء المشاركين لهدف معيّن:
    - فعليًا يطلق الدالة الخاصة بالهدف داخل معاملة واحدة
    - مناسب لزر فعل (POST فقط)
    """
    required_perms = ["performance.change_objective"]

    def get_permission_object(self):
        return get_object_or_404(Objective, pk=self.kwargs["pk"])

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        objective = self.get_permission_object()
        # استدعاء خدمة/دالة بناء المشاركين
        objective._rebuild_participants()
        messages.success(request, "Participants have been rebuilt successfully.")
        return HttpResponseRedirect(reverse_lazy("performance:objective_detail", kwargs={"pk": objective.pk}))
