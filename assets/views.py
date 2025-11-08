# assets/views.py
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DetailView

from base.views import BaseScopedListView, apply_search_filters
from . import models as m
from .forms import AssetCategoryForm, AssetForm, AssetAssignmentForm


# =======================
# Categories
# =======================
class AssetCategoryListView(LoginRequiredMixin, BaseScopedListView, ListView):
    model = m.AssetCategory
    template_name = "assets/category_list.html"
    paginate_by = 24

    def get_queryset(self):
        base = m.AssetCategory.acl_objects.with_acl("view")
        qs = m.AssetCategory.objects.filter(pk__in=base.values("pk")).select_related("company", "parent")
        qs = apply_search_filters(self.request, qs, search_fields=["name", "parent__name"])
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_add_category"] = self.request.user.has_perm("assets.add_assetcategory")
        change_ids = m.AssetCategory.acl_objects.with_acl("change").values_list("id", flat=True)
        ctx["category_change_ids"] = set(change_ids)
        return ctx


class AssetCategoryCreateView(LoginRequiredMixin, CreateView):
    model = m.AssetCategory
    form_class = AssetCategoryForm
    template_name = "assets/category_form.html"
    success_url = reverse_lazy("assets:category_list")

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw["request"] = self.request
        return kw


class AssetCategoryUpdateView(LoginRequiredMixin, UpdateView):
    model = m.AssetCategory
    form_class = AssetCategoryForm
    template_name = "assets/category_form.html"
    success_url = reverse_lazy("assets:category_list")

    def get_queryset(self):
        base = m.AssetCategory.acl_objects.with_acl("change")
        return (m.AssetCategory.objects
                .filter(pk__in=base.values("pk"))
                .select_related("company", "parent"))


class AssetCategoryDetailView(LoginRequiredMixin, DetailView):
    model = m.AssetCategory
    template_name = "assets/category_detail.html"

    def get_queryset(self):
        base = m.AssetCategory.acl_objects.with_acl("view")
        return (m.AssetCategory.objects
                .filter(pk__in=base.values("pk"))
                .select_related("company", "parent"))


# =======================
# Assets
# =======================
class AssetListView(LoginRequiredMixin, BaseScopedListView, ListView):
    model = m.Asset
    template_name = "assets/asset_list.html"
    paginate_by = 24

    def get_queryset(self):
        base = m.Asset.acl_objects.with_acl("view")
        qs = (
            m.Asset.objects.filter(pk__in=base.values("pk"))
            .select_related("company", "category", "department", "holder", "parent")
            .order_by("code", "name")
        )
        qs = apply_search_filters(
            self.request,
            qs,
            search_fields=["code", "name", "serial", "holder__name", "department__name", "category__name"],
        )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_add_asset"] = self.request.user.has_perm("assets.add_asset")
        change_ids = m.Asset.acl_objects.with_acl("change").values_list("id", flat=True)
        ctx["asset_change_ids"] = set(change_ids)
        return ctx


class AssetCreateView(LoginRequiredMixin, CreateView):
    model = m.Asset
    form_class = AssetForm
    template_name = "assets/asset_form.html"
    success_url = reverse_lazy("assets:asset_list")

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw["request"] = self.request
        return kw


class AssetUpdateView(LoginRequiredMixin, UpdateView):
    model = m.Asset
    form_class = AssetForm
    template_name = "assets/asset_form.html"
    success_url = reverse_lazy("assets:asset_list")

    def get_queryset(self):
        base = m.Asset.acl_objects.with_acl("change")
        return (m.Asset.objects
                .filter(pk__in=base.values("pk"))
                .select_related("company", "category", "department", "holder", "parent"))


class AssetDetailView(LoginRequiredMixin, DetailView):
    model = m.Asset
    template_name = "assets/asset_detail.html"

    def get_queryset(self):
        base = m.Asset.acl_objects.with_acl("view")
        return (m.Asset.objects
                .filter(pk__in=base.values("pk"))
                .select_related("company", "category", "department", "holder", "parent"))


# =======================
# Assignments
# =======================
class AssetAssignmentListView(LoginRequiredMixin, BaseScopedListView, ListView):
    model = m.AssetAssignment
    template_name = "assets/assignment_list.html"
    paginate_by = 24

    def get_queryset(self):
        base = m.AssetAssignment.acl_objects.with_acl("view")
        qs = (
            m.AssetAssignment.objects.filter(pk__in=base.values("pk"))
            .select_related("asset", "employee", "company")
            .order_by("-id")
        )
        qs = apply_search_filters(
            self.request,
            qs,
            search_fields=["asset__code", "asset__name", "employee__name", "note"],
        )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_add_assignment"] = self.request.user.has_perm("assets.add_assetassignment")
        change_ids = m.AssetAssignment.acl_objects.with_acl("change").values_list("id", flat=True)
        ctx["assignment_change_ids"] = set(change_ids)
        return ctx


class AssetAssignmentCreateView(LoginRequiredMixin, CreateView):
    model = m.AssetAssignment
    form_class = AssetAssignmentForm
    template_name = "assets/assignment_form.html"
    success_url = reverse_lazy("assets:assignment_list")

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw["request"] = self.request
        return kw


class AssetAssignmentUpdateView(LoginRequiredMixin, UpdateView):
    model = m.AssetAssignment
    form_class = AssetAssignmentForm
    template_name = "assets/assignment_form.html"
    success_url = reverse_lazy("assets:assignment_list")

    def get_queryset(self):
        base = m.AssetAssignment.acl_objects.with_acl("change")
        return (m.AssetAssignment.objects
                .filter(pk__in=base.values("pk"))
                .select_related("asset", "employee", "company"))


class AssetAssignmentDetailView(LoginRequiredMixin, DetailView):
    model = m.AssetAssignment
    template_name = "assets/assignment_detail.html"

    def get_queryset(self):
        base = m.AssetAssignment.acl_objects.with_acl("view")
        return (m.AssetAssignment.objects
                .filter(pk__in=base.values("pk"))
                .select_related("asset", "employee", "company"))
