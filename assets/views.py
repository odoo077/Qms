# assets/views.py
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import ListView

from base.views import (
    BaseScopedListView,
    BaseScopedDetailView,
    BaseScopedCreateView,
    BaseScopedUpdateView,
    apply_search_filters, BaseScopedDeleteView, ConfirmDeleteMixin,
)
from base.acl_service import has_perm
from . import models as m
from .forms import AssetCategoryForm, AssetForm, AssetAssignmentForm


# ============================================================
# Categories
# ============================================================

class AssetCategoryListView(LoginRequiredMixin, BaseScopedListView):
    model = m.AssetCategory
    template_name = "assets/category_list.html"
    paginate_by = 24

    def get_queryset(self):
        """
        BaseScopedListView already applies:
          - ACL with 'view' (via _apply_acl_on_queryset)
          - company scope (via _enforce_company_on_queryset)
        Here we only add select_related + search.
        """
        base_qs = super().get_queryset()
        qs = (
            base_qs
            .select_related("company", "parent")
            .order_by("name")
        )
        qs = apply_search_filters(
            self.request,
            qs,
            search_fields=["name", "parent__name"],
        )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_add_category"] = self.request.user.has_perm("assets.add_assetcategory")
        change_ids = m.AssetCategory.acl_objects.with_acl("change").values_list("id", flat=True)
        ctx["category_change_ids"] = set(change_ids)
        return ctx


class AssetCategoryCreateView(
    LoginRequiredMixin,
    PermissionRequiredMixin,
    BaseScopedCreateView,
):
    model = m.AssetCategory
    form_class = AssetCategoryForm
    template_name = "assets/category_form.html"
    success_url = reverse_lazy("assets:category_list")
    permission_required = "assets.add_assetcategory"

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        # pass request to form for company-based filtering or other logic
        kw["request"] = self.request
        return kw


class AssetCategoryUpdateView(
    LoginRequiredMixin,
    PermissionRequiredMixin,
    BaseScopedUpdateView,
):
    model = m.AssetCategory
    form_class = AssetCategoryForm
    template_name = "assets/category_form.html"
    success_url = reverse_lazy("assets:category_list")
    permission_required = ["assets.change_assetcategory", "assets.delete_assetcategory"]

    def get_queryset(self):
        base_qs = super().get_queryset()
        return base_qs.select_related("company", "parent")



class AssetCategoryDetailView(LoginRequiredMixin, BaseScopedDetailView):
    model = m.AssetCategory
    template_name = "assets/category_detail.html"

    def get_queryset(self):
        base_qs = super().get_queryset()
        return base_qs.select_related("company", "parent")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        obj = ctx.get("object")
        ctx["can_edit_object"] = bool(obj and has_perm(obj, self.request.user, "change"))
        ctx["can_delete_object"] = bool(obj and has_perm(obj, self.request.user, "delete"))
        return ctx

class AssetCategoryDeleteView(
    LoginRequiredMixin,
    PermissionRequiredMixin,
    ConfirmDeleteMixin,
    BaseScopedDeleteView,
):
    model = m.AssetCategory
    permission_required = "assets.delete_assetcategory"
    back_url_name = "assets:category_list"
    object_label_field = "name"



# ============================================================
# Assets
# ============================================================

class AssetListView(LoginRequiredMixin, BaseScopedListView):
    model = m.Asset
    template_name = "assets/asset_list.html"
    paginate_by = 24

    def get_queryset(self):
        """
        - BaseScopedListView handles ACL + company scope.
        - Here we enrich with select_related + search + ordering.
        """
        base_qs = super().get_queryset()
        qs = (
            base_qs
            .select_related("company", "category", "department", "holder", "parent")
            .order_by("code", "name")
        )
        qs = apply_search_filters(
            self.request,
            qs,
            search_fields=[
                "code",
                "name",
                "serial",
                "holder__name",
                "department__name",
                "category__name",
            ],
        )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_add_asset"] = self.request.user.has_perm("assets.add_asset")
        change_ids = m.Asset.acl_objects.with_acl("change").values_list("id", flat=True)
        ctx["asset_change_ids"] = set(change_ids)
        return ctx


class AssetCreateView(
    LoginRequiredMixin,
    PermissionRequiredMixin,
    BaseScopedCreateView,
):
    model = m.Asset
    form_class = AssetForm
    template_name = "assets/asset_form.html"
    success_url = reverse_lazy("assets:asset_list")
    permission_required = "assets.add_asset"

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw["request"] = self.request
        return kw


class AssetUpdateView(
    LoginRequiredMixin,
    PermissionRequiredMixin,
    BaseScopedUpdateView,
):
    model = m.Asset
    form_class = AssetForm
    template_name = "assets/asset_form.html"
    success_url = reverse_lazy("assets:asset_list")
    permission_required = ["assets.change_asset", "assets.delete_asset"]

    def get_queryset(self):
        base_qs = super().get_queryset()
        return base_qs.select_related("company", "category", "department", "holder", "parent")



class AssetDetailView(LoginRequiredMixin, BaseScopedDetailView):
    model = m.Asset
    template_name = "assets/asset_detail.html"

    def get_queryset(self):
        base_qs = super().get_queryset()
        return base_qs.select_related("company", "category", "department", "holder", "parent")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        obj = ctx.get("object")
        ctx["can_edit_object"] = bool(obj and has_perm(obj, self.request.user, "change"))
        ctx["can_delete_object"] = bool(obj and has_perm(obj, self.request.user, "delete"))
        return ctx

class AssetDeleteView(
    LoginRequiredMixin,
    PermissionRequiredMixin,
    ConfirmDeleteMixin,
    BaseScopedDeleteView,
):
    model = m.Asset
    permission_required = "assets.delete_asset"
    back_url_name = "assets:asset_list"
    object_label_field = "name"


# ============================================================
# Assignments
# ============================================================

class AssetAssignmentListView(LoginRequiredMixin, BaseScopedListView):
    model = m.AssetAssignment
    template_name = "assets/assignment_list.html"
    paginate_by = 24

    def get_queryset(self):
        base_qs = super().get_queryset()
        qs = (
            base_qs
            .select_related("asset", "employee", "company")
            .order_by("-id")
        )
        qs = apply_search_filters(
            self.request,
            qs,
            search_fields=[
                "asset__code",
                "asset__name",
                "employee__name",
                "note",
            ],
        )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_add_assignment"] = self.request.user.has_perm("assets.add_assetassignment")
        change_ids = m.AssetAssignment.acl_objects.with_acl("change").values_list("id", flat=True)
        ctx["assignment_change_ids"] = set(change_ids)
        return ctx


class AssetAssignmentCreateView(
    LoginRequiredMixin,
    PermissionRequiredMixin,
    BaseScopedCreateView,
):
    model = m.AssetAssignment
    form_class = AssetAssignmentForm
    template_name = "assets/assignment_form.html"
    success_url = reverse_lazy("assets:assignment_list")
    permission_required = "assets.add_assetassignment"

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw["request"] = self.request
        return kw


class AssetAssignmentUpdateView(
    LoginRequiredMixin,
    PermissionRequiredMixin,
    BaseScopedUpdateView,
):
    model = m.AssetAssignment
    form_class = AssetAssignmentForm
    template_name = "assets/assignment_form.html"
    success_url = reverse_lazy("assets:assignment_list")
    permission_required = ["assets.change_assetassignment", "assets.delete_assetassignment"]

    def get_queryset(self):
        base_qs = super().get_queryset()
        return base_qs.select_related("asset", "employee", "company")



class AssetAssignmentDetailView(LoginRequiredMixin, BaseScopedDetailView):
    model = m.AssetAssignment
    template_name = "assets/assignment_detail.html"

    def get_queryset(self):
        base_qs = super().get_queryset()
        return base_qs.select_related("asset", "employee", "company")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        obj = ctx.get("object")
        ctx["can_edit_object"] = bool(obj and has_perm(obj, self.request.user, "change"))
        ctx["can_delete_object"] = bool(obj and has_perm(obj, self.request.user, "delete"))
        return ctx

class AssetAssignmentDeleteView(
    LoginRequiredMixin,
    PermissionRequiredMixin,
    ConfirmDeleteMixin,
    BaseScopedDeleteView,
):
    model = m.AssetAssignment
    permission_required = "assets.delete_assetassignment"
    back_url_name = "assets:assignment_list"
    object_label_field = "asset"  # يظهر اسم الأصل المرتبط

