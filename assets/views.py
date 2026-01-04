# assets/views.py
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db.models import Prefetch
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse, reverse_lazy
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
    FormView,
)

from . import models as m
from .forms import (
    AssetCategoryForm,
    AssetForm,
    AssetAssignForm,
    AssetUnassignForm,
)
from .services import assign_asset, unassign_asset
from django.db import models
from django.apps import apps

# ============================================================
# Base mixin to inject request into forms
# ============================================================

class RequestFormKwargsMixin:
    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw["request"] = self.request
        return kw


# ============================================================
# Asset Categories
# ============================================================

class AssetCategoryListView(LoginRequiredMixin, ListView):
    model = m.AssetCategory
    template_name = "assets/category_list.html"
    paginate_by = 25
    ordering = ["name"]

    def get_queryset(self):
        qs = super().get_queryset().select_related("company", "parent")

        q = (self.request.GET.get("q") or "").strip()
        active = (self.request.GET.get("active") or "").strip()

        if q:
            qs = qs.filter(name__icontains=q)

        if active in {"0", "1"}:
            qs = qs.filter(active=(active == "1"))

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        base = m.AssetCategory.objects.all()
        ctx["active_count"] = base.filter(active=True).count()
        ctx["archived_count"] = base.filter(active=False).count()
        ctx["company_count"] = base.values("company_id").distinct().count()
        return ctx


class AssetCategoryCreateView(LoginRequiredMixin, RequestFormKwargsMixin, CreateView):
    model = m.AssetCategory
    form_class = AssetCategoryForm
    template_name = "assets/category_form.html"
    success_url = reverse_lazy("assets:category_list")


class AssetCategoryUpdateView(LoginRequiredMixin, RequestFormKwargsMixin, UpdateView):
    model = m.AssetCategory
    form_class = AssetCategoryForm
    template_name = "assets/category_form.html"
    success_url = reverse_lazy("assets:category_list")


class AssetCategoryDetailView(LoginRequiredMixin, DetailView):
    model = m.AssetCategory
    template_name = "assets/category_detail.html"


class AssetCategoryDeleteView(LoginRequiredMixin, DeleteView):
    model = m.AssetCategory
    template_name = "partials/confirm_delete.html"
    success_url = reverse_lazy("assets:category_list")


# ============================================================
# Assets
# ============================================================


class AssetListView(LoginRequiredMixin, ListView):
    model = m.Asset
    template_name = "assets/asset_list.html"
    paginate_by = 25
    ordering = ["code", "name"]

    def get_queryset(self):
        qs = (
            super()
            .get_queryset()
            .select_related("company", "category", "department", "holder", "parent")
        )

        # -------- Filters (GET) --------
        q = (self.request.GET.get("q") or "").strip()
        status = (self.request.GET.get("status") or "").strip()
        active = (self.request.GET.get("active") or "").strip()

        if q:
            qs = qs.filter(models.Q(code__icontains=q) | models.Q(name__icontains=q))

        if status in {
            m.Asset.Status.AVAILABLE,
            m.Asset.Status.ASSIGNED,
            m.Asset.Status.MAINTENANCE,
            m.Asset.Status.RETIRED,
        }:
            qs = qs.filter(status=status)

        if active in {"0", "1"}:
            qs = qs.filter(active=(active == "1"))

        # ✅ NEW: Assign-from-Employee context
        assign_to = self.request.GET.get("assign_to")
        if assign_to:
            qs = qs.filter(
                active=True,
                status=m.Asset.Status.AVAILABLE,  # فقط الأصول القابلة للإسناد
            )

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        base = m.Asset.objects.all()
        ctx["assigned_count"] = base.filter(status=m.Asset.Status.ASSIGNED).count()
        ctx["available_count"] = base.filter(status=m.Asset.Status.AVAILABLE).count()
        ctx["issue_count"] = base.filter(status=m.Asset.Status.MAINTENANCE).count()

        # ✅ Assign-from-Employee context
        assign_to = self.request.GET.get("assign_to")
        if assign_to:
            Employee = apps.get_model("hr", "Employee")
            employee = Employee.objects.filter(pk=assign_to).first()

            ctx["assign_to_employee"] = employee
            ctx["assign_mode"] = True
        else:
            ctx["assign_to_employee"] = None
            ctx["assign_mode"] = False

        return ctx


class AssetCreateView(LoginRequiredMixin, RequestFormKwargsMixin, CreateView):
    model = m.Asset
    form_class = AssetForm
    template_name = "assets/asset_form.html"
    success_url = reverse_lazy("assets:asset_list")


class AssetUpdateView(LoginRequiredMixin, RequestFormKwargsMixin, UpdateView):
    model = m.Asset
    form_class = AssetForm
    template_name = "assets/asset_form.html"
    success_url = reverse_lazy("assets:asset_list")


class AssetDetailView(LoginRequiredMixin, DetailView):
    model = m.Asset
    template_name = "assets/asset_detail.html"

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related(
                "company",
                "category",
                "department",
                "holder",
                "parent",
            )
            .prefetch_related(
                Prefetch(
                    "assignments",
                    queryset=(
                        m.AssetAssignment.objects
                        .select_related("employee", "company")
                        .order_by("-date_from", "-id")
                    ),
                )
            )
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        assignments = list(self.object.assignments.all())

        # الإسناد الحالي (واحد فقط كحد أقصى)
        current_assignment = next(
            (a for a in assignments if a.date_to is None),
            None
        )

        # التاريخ الكامل (بما فيه الحالي)
        ctx["current_assignment"] = current_assignment
        ctx["assignment_history"] = assignments

        return ctx


class AssetDeleteView(LoginRequiredMixin, DeleteView):
    model = m.Asset
    template_name = "partials/confirm_delete.html"
    success_url = reverse_lazy("assets:asset_list")


# ============================================================
# Workflow: Assign / Unassign
# ============================================================

class AssetAssignView(LoginRequiredMixin, FormView):
    template_name = "assets/asset_assign.html"

    def dispatch(self, request, *args, **kwargs):
        self.asset = get_object_or_404(m.Asset, pk=kwargs["pk"])

        # NEW: pre-selected employee (optional)
        self.assign_to_employee_id = request.GET.get("assign_to")

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["asset"] = self.asset
        return ctx

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw["request"] = self.request
        kw["asset"] = self.asset
        kw["assign_to_employee_id"] = self.assign_to_employee_id
        return kw

    def get_form_class(self):
        return AssetAssignForm

    def form_valid(self, form):
        try:
            employee = form.cleaned_data["employee"]
            date_from = form.cleaned_data.get("date_from")
            note = form.cleaned_data.get("note") or ""
            assign_asset(self.asset, employee.id, date_from=date_from, note=note)
            messages.success(self.request, "Asset assigned successfully.")
            return HttpResponseRedirect(reverse("assets:asset_detail", args=[self.asset.pk]))
        except ValidationError as e:
            # عرض رسالة واضحة بدون كسر الصفحة
            msg = getattr(e, "message", None) or str(e)
            form.add_error(None, msg)
            return self.form_invalid(form)


class AssetUnassignView(LoginRequiredMixin, FormView):
    template_name = "assets/asset_unassign.html"

    def dispatch(self, request, *args, **kwargs):
        self.asset = get_object_or_404(m.Asset, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["asset"] = self.asset
        return ctx

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw["request"] = self.request
        kw["asset"] = self.asset
        return kw

    def get_form_class(self):
        return AssetUnassignForm

    def form_valid(self, form):
        try:
            date_to = form.cleaned_data.get("date_to")
            note = form.cleaned_data.get("note") or ""
            unassign_asset(self.asset, date_to=date_to, note=note)
            messages.success(self.request, "Asset unassigned successfully.")
            return HttpResponseRedirect(reverse("assets:asset_detail", args=[self.asset.pk]))
        except ValidationError as e:
            msg = getattr(e, "message", None) or str(e)
            form.add_error(None, msg)
            return self.form_invalid(form)


# ============================================================
# Assignments (Read-only History)
# ============================================================

class AssetAssignmentListView(LoginRequiredMixin, ListView):
    model = m.AssetAssignment
    template_name = "assets/assignment_list.html"
    paginate_by = 25
    ordering = ["-id"]

    def get_queryset(self):
        qs = (
            super()
            .get_queryset()
            .select_related("asset", "employee", "company")
        )

        # ==============================
        # Query params
        # ==============================
        q = (self.request.GET.get("q") or "").strip()
        state = (self.request.GET.get("state") or "").strip()  # open | closed

        # ==============================
        # Search
        # ==============================
        if q:
            qs = qs.filter(
                models.Q(asset__code__icontains=q)
                | models.Q(asset__name__icontains=q)
                | models.Q(employee__name__icontains=q)
            )

        # ==============================
        # State filter (CORRECT)
        # ==============================
        if state == "open":
            qs = qs.filter(date_to__isnull=True)
        elif state == "closed":
            qs = qs.filter(date_to__isnull=False)

        return qs

class AssetAssignmentDetailView(LoginRequiredMixin, DetailView):
    model = m.AssetAssignment
    template_name = "assets/assignment_detail.html"


class AssetAssignmentDeleteView(LoginRequiredMixin, DeleteView):
    """
    الحذف هنا ليس Workflow، لكنه قد تحتاجه إداريًا.
    أبقيناه كخيار، ويمكن إلغاؤه لاحقًا إن رغبت.
    """
    model = m.AssetAssignment
    template_name = "partials/confirm_delete.html"
    success_url = reverse_lazy("assets:assignment_list")
