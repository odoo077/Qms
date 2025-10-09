# assets/views/employee_assets.py
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, View, DetailView, FormView
from django.contrib import messages
from django.utils import timezone
from base.security import ObjectActionPermissionMixin

from assets.models import EmployeeAsset, AssetItem
from assets.forms import (
    EmployeeAssetAssignForm,
    EmployeeAssetReturnForm,
    EmployeeAssetTransferForm,
)
from assets.services.assignment_service import AssignmentService
from .base import CompanyContextMixin, SuccessMessageMixin


# --------- قائمة سجلات التسليم ----------
class EmployeeAssetListView(CompanyContextMixin, ListView):
    model = EmployeeAsset
    template_name = "assets/employee_assets/employee_asset_list.html"
    context_object_name = "assignments"
    paginate_by = 25

    def get_queryset(self):
        qs = EmployeeAsset.objects.select_related(
            "employee", "employee__department", "item", "item__model", "item__model__type"
        ).order_by("-date_assigned")
        if self.company:
            qs = qs.filter(company=self.company)
        active = self.request.GET.get("active")
        if active in {"1", "true", "True"}:
            qs = qs.filter(is_active=True)
        return qs


# --------- إنشاء تسليم (Assign) ----------
class EmployeeAssetAssignView(ObjectActionPermissionMixin, CompanyContextMixin, SuccessMessageMixin, CreateView):
    required_perm_app = "assets"
    required_perm_codename = "assign_item"

    model = EmployeeAsset
    form_class = EmployeeAssetAssignForm
    template_name = "assets/employee_assets/employee_asset_assign.html"
    success_message = "Asset assigned successfully."

    def get_initial(self):
        initial = super().get_initial()
        item_id = self.request.GET.get("item")
        if item_id:
            initial["item"] = item_id
        initial.setdefault("date_assigned", timezone.now().date())
        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["company"] = self.company
        return kwargs


    def form_valid(self, form):
        # فحص صلاحية الإسناد على عنصر الأصل
        self.check_action_perm(form.cleaned_data["item"])

        # استخدم الخدمة للضمان الذرّي
        rec = AssignmentService.assign_item(
            item=form.cleaned_data["item"],
            employee=form.cleaned_data["employee"],
            date_assigned=form.cleaned_data.get("date_assigned"),
            due_back=form.cleaned_data.get("due_back"),
            note=form.cleaned_data.get("handover_note") or "",
        )
        messages.success(self.request, self.success_message)
        return redirect(self.get_success_url())

    def get_success_url(self):
        next_url = self.request.GET.get("next")
        return next_url or reverse_lazy("assets:employee_asset_list")


# --------- إرجاع أصل (Return) ----------
class EmployeeAssetReturnView(CompanyContextMixin, SuccessMessageMixin, UpdateView):
    model = EmployeeAsset
    form_class = EmployeeAssetReturnForm
    template_name = "assets/employee_assets/employee_asset_return.html"
    success_message = "Asset returned successfully."

    def get_queryset(self):
        qs = super().get_queryset().select_related("item")
        if self.company:
            qs = qs.filter(company=self.company)
        return qs

    def form_valid(self, form):
        AssignmentService.return_item(self.object,
                                      date_returned=form.cleaned_data.get("date_returned"),
                                      note=form.cleaned_data.get("return_note") or "")
        messages.success(self.request, self.success_message)
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse_lazy("assets:employee_asset_list")


# --------- تحويل أصل (Transfer) ----------
class EmployeeAssetTransferView(ObjectActionPermissionMixin, CompanyContextMixin, FormView):
    required_perm_app = "assets"
    required_perm_codename = "transfer_item"

    form_class = EmployeeAssetTransferForm
    template_name = "assets/employee_assets/employee_asset_transfer.html"

    def dispatch(self, request, *args, **kwargs):
        self.item = get_object_or_404(AssetItem, pk=kwargs["item_pk"])
        if self.company:
            if self.item.company_id != self.company.id:
                messages.error(request, "Item does not belong to current company.")
                return redirect("assets:asset_item_list")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["company"] = self.company
        kwargs["item"] = self.item
        return kwargs

    def form_valid(self, form):
        self.check_action_perm(self.item)

        AssignmentService.transfer_item(
            item=self.item,
            to_employee=form.cleaned_data["to_employee"],
            date_assigned=form.cleaned_data.get("date_assigned"),
            due_back=form.cleaned_data.get("due_back"),
            note=form.cleaned_data.get("note") or "",
        )
        messages.success(self.request, "Asset transferred successfully.")
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse_lazy("assets:asset_item_detail", kwargs={"pk": self.item.pk})
