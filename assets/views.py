# assets/views.py
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import models
from django.db.models import Prefetch, Q
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
from django.apps import apps

from base.company_context import get_allowed_company_ids, get_company_id
from . import models as m
from .forms import (
    AssetCategoryForm,
    AssetForm,
    AssetAssignForm,
    AssetUnassignForm,
)
from .services import assign_asset, unassign_asset


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

    # ترتيب افتراضي
    ordering = ["name"]

    # --------------------------------------------
    # Queryset (Scoped + Filtered)
    # --------------------------------------------
    def get_queryset(self):
        qs = (
            m.AssetCategory.objects
            .select_related("company", "parent")
        )

        # ------------------------------------------------
        # Company Scope (إجباري)
        # ------------------------------------------------
        allowed_company_ids = get_allowed_company_ids(self.request)
        if allowed_company_ids:
            qs = qs.filter(company_id__in=allowed_company_ids)
        else:
            return qs.none()

        # ------------------------------------------------
        # Search (name + parent name)
        # ------------------------------------------------
        q = (self.request.GET.get("q") or "").strip()
        if q:
            qs = qs.filter(
                Q(name__icontains=q) |
                Q(parent__name__icontains=q)
            )

        # ------------------------------------------------
        # Active filter
        # ------------------------------------------------
        active = (self.request.GET.get("active") or "").strip()
        if active in {"0", "1"}:
            qs = qs.filter(active=(active == "1"))

        # ------------------------------------------------
        # Company filter (explicit – useful for superuser)
        # ------------------------------------------------
        company = (self.request.GET.get("company") or "").strip()
        if company.isdigit():
            qs = qs.filter(company_id=int(company))

        # ------------------------------------------------
        # Parent filter (root / child)
        # ------------------------------------------------
        has_parent = (self.request.GET.get("has_parent") or "").strip()
        if has_parent == "1":
            qs = qs.filter(parent__isnull=False)
        elif has_parent == "0":
            qs = qs.filter(parent__isnull=True)

        # ------------------------------------------------
        # Ordering (safe whitelist)
        # ------------------------------------------------
        order = (self.request.GET.get("order") or "").strip()
        ORDERING_MAP = {
            "name": "name",
            "-name": "-name",
            "company": "company__name",
            "-company": "-company__name",
            "latest": "-id",
        }
        if order in ORDERING_MAP:
            qs = qs.order_by(ORDERING_MAP[order])
        else:
            qs = qs.order_by("name")

        return qs

    # --------------------------------------------
    # Context
    # --------------------------------------------
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        # استخدم نفس queryset لضمان consistency
        base = self.object_list

        ctx.update({
            # KPIs (Scoped)
            "active_count": base.filter(active=True).count(),
            "archived_count": base.filter(active=False).count(),
            "company_count": base.values("company_id").distinct().count(),

            # Preserve filters (UX)
            "filters": {
                "q": self.request.GET.get("q", ""),
                "active": self.request.GET.get("active", ""),
                "company": self.request.GET.get("company", ""),
                "has_parent": self.request.GET.get("has_parent", ""),
                "order": self.request.GET.get("order", ""),
            },
        })

        return ctx


class AssetCategoryDetailView(LoginRequiredMixin, DetailView):
    """
    Asset Category Detail View (Production-grade)

    Rules:
    - Enforce Company Scope (allowed companies)
    - Read-only structural view
    - Optimized related loading
    """

    model = m.AssetCategory
    template_name = "assets/category_detail.html"

    # --------------------------------------------------
    # Queryset (optimized)
    # --------------------------------------------------
    def get_queryset(self):
        return (
            m.AssetCategory.objects
            .select_related("company", "parent")
        )

    # --------------------------------------------------
    # Object-level security (Company Scope)
    # --------------------------------------------------
    def get_object(self, queryset=None):
        obj = super().get_object(queryset)

        allowed_company_ids = get_allowed_company_ids(self.request)

        # Superuser bypass (اختياري لكنه Best Practice)
        if self.request.user.is_superuser:
            return obj

        if obj.company_id and obj.company_id not in allowed_company_ids:
            raise PermissionDenied("You do not have access to this category.")

        return obj

    # --------------------------------------------------
    # Context
    # --------------------------------------------------
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        category = self.object

        ctx.update({
            # Permissions / actions
            "can_edit_object": True,
            "can_delete_object": True,

            # Hierarchy info
            "is_root": category.parent_id is None,
            "children": (
                category.children
                .filter(active=True)
                .order_by("name")
            ),

            # Flags (explicit for template clarity)
            "category_state": {
                "active": category.active,
                "has_parent": bool(category.parent_id),
                "has_children": category.children.exists(),
            },
        })

        return ctx




class AssetCategoryCreateView(
    LoginRequiredMixin,
    RequestFormKwargsMixin,
    CreateView
):
    model = m.AssetCategory
    form_class = AssetCategoryForm
    template_name = "assets/category_form.html"
    success_url = reverse_lazy("assets:category_list")

    # --------------------------------------------
    # Initial values (UX)
    # --------------------------------------------
    def get_initial(self):
        initial = super().get_initial()

        # Default company = current company context (if allowed)
        cid = get_company_id(self.request)
        allowed_ids = get_allowed_company_ids(self.request)

        if cid and cid in allowed_ids:
            initial.setdefault("company", cid)

        return initial

    # --------------------------------------------
    # Final validation before save
    # --------------------------------------------
    def form_valid(self, form):
        company = form.cleaned_data.get("company")
        allowed_ids = get_allowed_company_ids(self.request)

        # Safety: company must be within allowed scope
        if company and company.id not in allowed_ids:
            raise PermissionDenied("Company is outside allowed scope.")

        return super().form_valid(form)



class AssetCategoryUpdateView(
    LoginRequiredMixin,
    RequestFormKwargsMixin,
    UpdateView
):
    model = m.AssetCategory
    form_class = AssetCategoryForm
    template_name = "assets/category_form.html"
    success_url = reverse_lazy("assets:category_list")

    # --------------------------------------------
    # Queryset (Company Scope)
    # --------------------------------------------
    def get_queryset(self):
        qs = (
            m.AssetCategory.objects
            .select_related("company", "parent")
        )

        allowed_ids = get_allowed_company_ids(self.request)

        # Superuser bypass (best practice)
        if self.request.user.is_superuser:
            return qs

        return qs.filter(company_id__in=allowed_ids)

    # --------------------------------------------
    # Object-level protection
    # --------------------------------------------
    def get_object(self, queryset=None):
        obj = super().get_object(queryset)

        allowed_ids = get_allowed_company_ids(self.request)

        if not self.request.user.is_superuser:
            if obj.company_id not in allowed_ids:
                raise PermissionDenied(
                    "You do not have access to this category."
                )

        return obj

    # --------------------------------------------
    # Final validation before save
    # --------------------------------------------
    def form_valid(self, form):
        obj = form.instance
        allowed_ids = get_allowed_company_ids(self.request)

        # Company must remain within allowed scope
        if obj.company_id and obj.company_id not in allowed_ids:
            raise PermissionDenied("Company is outside allowed scope.")

        return super().form_valid(form)


class AssetCategoryDeleteView(LoginRequiredMixin, DeleteView):
    """
    Asset Category Delete View (Production-grade)

    Rules:
    - Enforce Company Scope
    - Prevent deletion if category has children
    - Prevent deletion if category is used by any Asset
    - Soft-fail with clear message (UI-friendly)
    """

    model = m.AssetCategory
    template_name = "partials/confirm_delete.html"
    success_url = reverse_lazy("assets:category_list")

    # --------------------------------------------------
    # Queryset (Company Scope)
    # --------------------------------------------------
    def get_queryset(self):
        qs = m.AssetCategory.objects.select_related("company", "parent")

        allowed_ids = get_allowed_company_ids(self.request)

        # Superuser bypass
        if self.request.user.is_superuser:
            return qs

        return qs.filter(company_id__in=allowed_ids)

    # --------------------------------------------------
    # Object-level protection
    # --------------------------------------------------
    def get_object(self, queryset=None):
        obj = super().get_object(queryset)

        allowed_ids = get_allowed_company_ids(self.request)

        if not self.request.user.is_superuser:
            if obj.company_id not in allowed_ids:
                raise PermissionDenied("You do not have access to this category.")

        return obj

    # --------------------------------------------------
    # Deletion policy
    # --------------------------------------------------
    def delete(self, request, *args, **kwargs):
        obj = self.get_object()

        # 1) Prevent deletion if has children
        if obj.children.exists():
            from django.contrib import messages
            messages.error(
                request,
                "Cannot delete a category that has child categories."
            )
            return self._redirect_back()

        # 2) Prevent deletion if used by assets
        if hasattr(obj, "assets") and obj.assets.exists():
            from django.contrib import messages
            messages.error(
                request,
                "Cannot delete a category that is used by assets."
            )
            return self._redirect_back()

        return super().delete(request, *args, **kwargs)

    # --------------------------------------------------
    # Safe redirect helper
    # --------------------------------------------------
    def _redirect_back(self):
        from django.shortcuts import redirect
        return redirect(self.success_url)



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
            m.Asset.objects
            .select_related(
                "company",
                "category",
                "department",
                "holder",
                "parent",
            )
        )

        # ------------------------------------------------
        # Company Scope (إجباري)
        # ------------------------------------------------
        allowed_company_ids = get_allowed_company_ids(self.request)
        if allowed_company_ids:
            qs = qs.filter(company_id__in=allowed_company_ids)
        else:
            return qs.none()

        # ------------------------------------------------
        # Filters
        # ------------------------------------------------
        q = (self.request.GET.get("q") or "").strip()
        status = (self.request.GET.get("status") or "").strip()
        active = (self.request.GET.get("active") or "").strip()
        category = (self.request.GET.get("category") or "").strip()
        department = (self.request.GET.get("department") or "").strip()
        has_holder = (self.request.GET.get("has_holder") or "").strip()  # 1|0
        is_child = (self.request.GET.get("is_child") or "").strip()      # 1|0
        company = (self.request.GET.get("company") or "").strip()
        order = (self.request.GET.get("order") or "").strip()

        # Search: code/name/serial (ERP search)
        if q:
            qs = qs.filter(
                Q(code__icontains=q)
                | Q(name__icontains=q)
                | Q(serial__icontains=q)
            )

        # Status (show all, including assigned, even if form can't set it)
        valid_statuses = {v for (v, _) in m.Asset.Status.choices}
        if status in valid_statuses:
            qs = qs.filter(status=status)

        # Active
        if active in {"0", "1"}:
            qs = qs.filter(active=(active == "1"))

        # Company (explicit filter; still within allowed scope)
        if company.isdigit():
            qs = qs.filter(company_id=int(company))

        # Category
        if category.isdigit():
            qs = qs.filter(category_id=int(category))

        # Department
        if department.isdigit():
            qs = qs.filter(department_id=int(department))

        # Holder flag
        if has_holder == "1":
            qs = qs.filter(holder__isnull=False)
        elif has_holder == "0":
            qs = qs.filter(holder__isnull=True)

        # Child assets (has parent)
        if is_child == "1":
            qs = qs.filter(parent__isnull=False)
        elif is_child == "0":
            qs = qs.filter(parent__isnull=True)

        # Assign-from-Employee context: show only assignable assets
        assign_to = (self.request.GET.get("assign_to") or "").strip()
        if assign_to:
            qs = qs.filter(active=True, status=m.Asset.Status.AVAILABLE)

        # ------------------------------------------------
        # Ordering (safe whitelist)
        # ------------------------------------------------
        ORDERING_MAP = {
            "code": "code",
            "-code": "-code",
            "name": "name",
            "-name": "-name",
            "status": "status",
            "-status": "-status",
            "company": "company__name",
            "-company": "-company__name",
            "latest": "-id",
        }
        qs = qs.order_by(ORDERING_MAP.get(order, "code"), "name")

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        # ------------------------------------------------
        # Scoped KPIs (within allowed companies)
        # ------------------------------------------------
        allowed_company_ids = get_allowed_company_ids(self.request)
        base = m.Asset.objects.filter(company_id__in=allowed_company_ids)

        ctx["assigned_count"] = base.filter(status=m.Asset.Status.ASSIGNED).count()
        ctx["available_count"] = base.filter(status=m.Asset.Status.AVAILABLE).count()
        ctx["issue_count"] = base.filter(status=m.Asset.Status.MAINTENANCE).count()
        ctx["retired_count"] = base.filter(status=m.Asset.Status.RETIRED).count()

        # Assign-from-Employee context
        assign_to = (self.request.GET.get("assign_to") or "").strip()
        if assign_to and assign_to.isdigit():
            Employee = apps.get_model("hr", "Employee")
            ctx["assign_to_employee"] = Employee.objects.filter(pk=int(assign_to)).first()
            ctx["assign_mode"] = True
        else:
            ctx["assign_to_employee"] = None
            ctx["assign_mode"] = False

        # Filters preservation for UI
        ctx["filters"] = {
            "q": self.request.GET.get("q", ""),
            "status": self.request.GET.get("status", ""),
            "active": self.request.GET.get("active", ""),
            "company": self.request.GET.get("company", ""),
            "category": self.request.GET.get("category", ""),
            "department": self.request.GET.get("department", ""),
            "has_holder": self.request.GET.get("has_holder", ""),
            "is_child": self.request.GET.get("is_child", ""),
            "order": self.request.GET.get("order", ""),
            "assign_to": self.request.GET.get("assign_to", ""),
        }

        return ctx


class AssetCreateView(LoginRequiredMixin, RequestFormKwargsMixin, CreateView):
    model = m.Asset
    form_class = AssetForm
    template_name = "assets/asset_form.html"
    success_url = reverse_lazy("assets:asset_list")

    def get_initial(self):
        initial = super().get_initial()

        cid = get_company_id(self.request)
        allowed_ids = get_allowed_company_ids(self.request)
        if cid and cid in allowed_ids:
            initial.setdefault("company", cid)

        return initial

    def form_valid(self, form):
        company = form.cleaned_data.get("company")
        allowed_ids = get_allowed_company_ids(self.request)

        if company and company.id not in allowed_ids and not self.request.user.is_superuser:
            raise PermissionDenied("Company is outside allowed scope.")

        return super().form_valid(form)


class AssetUpdateView(LoginRequiredMixin, RequestFormKwargsMixin, UpdateView):
    model = m.Asset
    form_class = AssetForm
    template_name = "assets/asset_form.html"
    success_url = reverse_lazy("assets:asset_list")

    def get_queryset(self):
        qs = (
            m.Asset.objects
            .select_related("company", "category", "department", "holder", "parent")
        )
        allowed_ids = get_allowed_company_ids(self.request)
        if self.request.user.is_superuser:
            return qs
        return qs.filter(company_id__in=allowed_ids)

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        allowed_ids = get_allowed_company_ids(self.request)

        if not self.request.user.is_superuser and obj.company_id not in allowed_ids:
            raise PermissionDenied("You do not have access to this asset.")

        return obj

    def form_valid(self, form):
        obj = form.instance
        allowed_ids = get_allowed_company_ids(self.request)

        if not self.request.user.is_superuser and obj.company_id not in allowed_ids:
            raise PermissionDenied("Company is outside allowed scope.")

        return super().form_valid(form)


class AssetDetailView(LoginRequiredMixin, DetailView):
    model = m.Asset
    template_name = "assets/asset_detail.html"

    def get_queryset(self):
        qs = (
            m.Asset.objects
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

        allowed_ids = get_allowed_company_ids(self.request)
        if self.request.user.is_superuser:
            return qs
        return qs.filter(company_id__in=allowed_ids)

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        allowed_ids = get_allowed_company_ids(self.request)

        if not self.request.user.is_superuser and obj.company_id not in allowed_ids:
            raise PermissionDenied("You do not have access to this asset.")

        return obj

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        assignments = list(self.object.assignments.all())
        current_assignment = next((a for a in assignments if a.date_to is None), None)

        ctx["current_assignment"] = current_assignment
        ctx["assignment_history"] = assignments

        # Useful flags for UI
        ctx["asset_state"] = {
            "active": bool(self.object.active),
            "is_assigned": self.object.status == m.Asset.Status.ASSIGNED,
            "has_parent": bool(self.object.parent_id),
            "has_children": self.object.children.exists(),
        }

        return ctx


class AssetDeleteView(LoginRequiredMixin, DeleteView):
    model = m.Asset
    template_name = "partials/confirm_delete.html"
    success_url = reverse_lazy("assets:asset_list")

    def get_queryset(self):
        qs = (
            m.Asset.objects
            .select_related("company")
        )
        allowed_ids = get_allowed_company_ids(self.request)
        if self.request.user.is_superuser:
            return qs
        return qs.filter(company_id__in=allowed_ids)

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        allowed_ids = get_allowed_company_ids(self.request)

        if not self.request.user.is_superuser and obj.company_id not in allowed_ids:
            raise PermissionDenied("You do not have access to this asset.")

        return obj

    def delete(self, request, *args, **kwargs):
        obj = self.get_object()

        # منع حذف أصل له children
        if obj.children.exists():
            messages.error(request, "Cannot delete an asset that has child assets.")
            return self._redirect_back()

        # منع حذف أصل لديه تاريخ إسنادات
        if hasattr(obj, "assignments") and obj.assignments.exists():
            messages.error(request, "Cannot delete an asset that has assignment history.")
            return self._redirect_back()

        return super().delete(request, *args, **kwargs)

    def _redirect_back(self):
        from django.shortcuts import redirect
        return redirect(self.success_url)




# ============================================================
# Workflow: Assign Asset
# ============================================================

class AssetAssignView(LoginRequiredMixin, FormView):
    """
    Assign Asset Workflow View (Production-grade)

    Rules:
    - Asset must be ACTIVE
    - Asset status must be AVAILABLE
    - Enforce company scope
    - All business logic handled in services.assign_asset
    """

    template_name = "assets/asset_assign.html"
    form_class = AssetAssignForm

    # --------------------------------------------------
    # Bootstrap
    # --------------------------------------------------
    def dispatch(self, request, *args, **kwargs):
        self.asset = get_object_or_404(
            m.Asset.objects.select_related("company"),
            pk=kwargs["pk"],
        )

        self.assign_to_employee_id = request.GET.get("assign_to")

        # Company scope enforcement
        if not request.user.is_superuser:
            allowed_ids = get_allowed_company_ids(request)
            if self.asset.company_id not in allowed_ids:
                raise PermissionDenied("You do not have access to this asset.")

        # State validation
        if not self.asset.active or self.asset.status != m.Asset.Status.AVAILABLE:
            messages.error(
                request,
                "Only active and available assets can be assigned."
            )
            return HttpResponseRedirect(
                reverse("assets:asset_detail", args=[self.asset.pk])
            )

        return super().dispatch(request, *args, **kwargs)

    # --------------------------------------------------
    # Context
    # --------------------------------------------------
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["asset"] = self.asset
        return ctx

    # --------------------------------------------------
    # Form wiring
    # --------------------------------------------------
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({
            "request": self.request,
            "asset": self.asset,
            "assign_to_employee_id": self.assign_to_employee_id,
        })
        return kwargs

    # --------------------------------------------------
    # Submit
    # --------------------------------------------------
    def form_valid(self, form):
        try:
            assign_asset(
                asset=self.asset,
                employee_id=form.cleaned_data["employee"].id,
                date_from=form.cleaned_data.get("date_from"),
                note=form.cleaned_data.get("note") or "",
            )

            messages.success(self.request, "Asset assigned successfully.")
            return HttpResponseRedirect(
                reverse("assets:asset_detail", args=[self.asset.pk])
            )

        except ValidationError as e:
            form.add_error(None, str(e))
            return self.form_invalid(form)


# ============================================================
# Workflow: Unassign Asset
# ============================================================

class AssetUnassignView(LoginRequiredMixin, FormView):
    """
    Unassign Asset Workflow View (Production-grade)

    Rules:
    - Asset must be ASSIGNED
    - Active assignment must exist
    - Enforce company scope
    - All business logic handled in services.unassign_asset
    """

    template_name = "assets/asset_unassign.html"
    form_class = AssetUnassignForm

    # --------------------------------------------------
    # Bootstrap
    # --------------------------------------------------
    def dispatch(self, request, *args, **kwargs):
        self.asset = get_object_or_404(
            m.Asset.objects.select_related("company"),
            pk=kwargs["pk"],
        )

        # Company scope enforcement
        if not request.user.is_superuser:
            allowed_ids = get_allowed_company_ids(request)
            if self.asset.company_id not in allowed_ids:
                raise PermissionDenied("You do not have access to this asset.")

        # State validation
        if self.asset.status != m.Asset.Status.ASSIGNED:
            messages.error(
                request,
                "Only assigned assets can be unassigned."
            )
            return HttpResponseRedirect(
                reverse("assets:asset_detail", args=[self.asset.pk])
            )

        return super().dispatch(request, *args, **kwargs)

    # --------------------------------------------------
    # Context
    # --------------------------------------------------
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["asset"] = self.asset
        return ctx

    # --------------------------------------------------
    # Form wiring
    # --------------------------------------------------
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({
            "request": self.request,
            "asset": self.asset,
        })
        return kwargs

    # --------------------------------------------------
    # Submit
    # --------------------------------------------------
    def form_valid(self, form):
        try:
            unassign_asset(
                asset=self.asset,
                date_to=form.cleaned_data.get("date_to"),
                note=form.cleaned_data.get("note") or "",
            )

            messages.success(self.request, "Asset unassigned successfully.")
            return HttpResponseRedirect(
                reverse("assets:asset_detail", args=[self.asset.pk])
            )

        except ValidationError as e:
            form.add_error(None, str(e))
            return self.form_invalid(form)



# ============================================================
# Asset Assignments (Read-only History)
# ============================================================

class AssetAssignmentListView(LoginRequiredMixin, ListView):
    """
    Asset Assignment History (Read-only)

    Features:
    - Company-scoped
    - Search by asset / employee
    - Filter by state (open / closed)
    """

    model = m.AssetAssignment
    template_name = "assets/assignment_list.html"
    paginate_by = 25
    ordering = ["-id"]

    # --------------------------------------------------
    # Queryset
    # --------------------------------------------------
    def get_queryset(self):
        qs = (
            m.AssetAssignment.objects
            .select_related("asset", "employee", "company")
        )

        # Company scope
        if not self.request.user.is_superuser:
            allowed_ids = get_allowed_company_ids(self.request)
            qs = qs.filter(company_id__in=allowed_ids)

        # Filters
        q = (self.request.GET.get("q") or "").strip()
        state = (self.request.GET.get("state") or "").strip()  # open | closed

        if q:
            qs = qs.filter(
                models.Q(asset__code__icontains=q)
                | models.Q(asset__name__icontains=q)
                | models.Q(employee__name__icontains=q)
            )

        if state == "open":
            qs = qs.filter(date_to__isnull=True)
        elif state == "closed":
            qs = qs.filter(date_to__isnull=False)

        return qs

    # --------------------------------------------------
    # Context
    # --------------------------------------------------
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        base = self.get_queryset()
        ctx["open_count"] = base.filter(date_to__isnull=True).count()
        ctx["closed_count"] = base.filter(date_to__isnull=False).count()
        ctx["total_count"] = base.count()

        ctx["filters"] = {
            "q": self.request.GET.get("q", ""),
            "state": self.request.GET.get("state", ""),
        }

        return ctx


# ============================================================
# Asset Assignment Detail
# ============================================================

class AssetAssignmentDetailView(LoginRequiredMixin, DetailView):
    """
    Assignment Detail (Read-only)

    Displays:
    - Asset
    - Employee
    - Period
    - Notes
    """

    model = m.AssetAssignment
    template_name = "assets/assignment_detail.html"

    # --------------------------------------------------
    # Queryset
    # --------------------------------------------------
    def get_queryset(self):
        qs = (
            m.AssetAssignment.objects
            .select_related("asset", "employee", "company")
        )

        if self.request.user.is_superuser:
            return qs

        allowed_ids = get_allowed_company_ids(self.request)
        return qs.filter(company_id__in=allowed_ids)

    # --------------------------------------------------
    # Object-level protection
    # --------------------------------------------------
    def get_object(self, queryset=None):
        obj = super().get_object(queryset)

        if not self.request.user.is_superuser:
            allowed_ids = get_allowed_company_ids(self.request)
            if obj.company_id not in allowed_ids:
                raise PermissionDenied("You do not have access to this assignment.")

        return obj


# ============================================================
# Asset Assignment Delete (Administrative only)
# ============================================================

class AssetAssignmentDeleteView(LoginRequiredMixin, DeleteView):
    """
    Administrative delete of assignment record.

    Notes:
    - NOT a workflow action
    - Should be used with care
    - Does NOT modify asset status
    """

    model = m.AssetAssignment
    template_name = "partials/confirm_delete.html"
    success_url = reverse_lazy("assets:assignment_list")

    # --------------------------------------------------
    # Queryset
    # --------------------------------------------------
    def get_queryset(self):
        qs = m.AssetAssignment.objects.select_related("company")

        if self.request.user.is_superuser:
            return qs

        allowed_ids = get_allowed_company_ids(self.request)
        return qs.filter(company_id__in=allowed_ids)

    # --------------------------------------------------
    # Safety note
    # --------------------------------------------------
    def delete(self, request, *args, **kwargs):
        """
        Deleting an assignment does NOT update asset state.
        This is intentional and administrative.
        """
        return super().delete(request, *args, **kwargs)

