from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
)

from . import models as m
from .forms import (
    AssetCategoryForm,
    AssetForm,
    AssetAssignmentForm,
)

# ============================================================
# Asset Categories
# ============================================================

class AssetCategoryListView(LoginRequiredMixin, ListView):
    model = m.AssetCategory
    template_name = "assets/category_list.html"
    paginate_by = 25
    ordering = ["name"]


class AssetCategoryCreateView(LoginRequiredMixin, CreateView):
    model = m.AssetCategory
    form_class = AssetCategoryForm
    template_name = "assets/category_form.html"
    success_url = reverse_lazy("assets:category_list")


class AssetCategoryUpdateView(LoginRequiredMixin, UpdateView):
    model = m.AssetCategory
    form_class = AssetCategoryForm
    template_name = "assets/category_form.html"
    success_url = reverse_lazy("assets:category_list")


class AssetCategoryDetailView(LoginRequiredMixin, DetailView):
    model = m.AssetCategory
    template_name = "assets/category_detail.html"


class AssetCategoryDeleteView(LoginRequiredMixin, DeleteView):
    model = m.AssetCategory
    template_name = "confirm_delete.html"
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
        )


class AssetCreateView(LoginRequiredMixin, CreateView):
    model = m.Asset
    form_class = AssetForm
    template_name = "assets/asset_form.html"
    success_url = reverse_lazy("assets:asset_list")


class AssetUpdateView(LoginRequiredMixin, UpdateView):
    model = m.Asset
    form_class = AssetForm
    template_name = "assets/asset_form.html"
    success_url = reverse_lazy("assets:asset_list")


class AssetDetailView(LoginRequiredMixin, DetailView):
    model = m.Asset
    template_name = "assets/asset_detail.html"


class AssetDeleteView(LoginRequiredMixin, DeleteView):
    model = m.Asset
    template_name = "confirm_delete.html"
    success_url = reverse_lazy("assets:asset_list")


# ============================================================
# Asset Assignments
# ============================================================

class AssetAssignmentListView(LoginRequiredMixin, ListView):
    model = m.AssetAssignment
    template_name = "assets/assignment_list.html"
    paginate_by = 25
    ordering = ["-id"]

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related(
                "asset",
                "employee",
                "company",
            )
        )


class AssetAssignmentCreateView(LoginRequiredMixin, CreateView):
    model = m.AssetAssignment
    form_class = AssetAssignmentForm
    template_name = "assets/assignment_form.html"
    success_url = reverse_lazy("assets:assignment_list")


class AssetAssignmentUpdateView(LoginRequiredMixin, UpdateView):
    model = m.AssetAssignment
    form_class = AssetAssignmentForm
    template_name = "assets/assignment_form.html"
    success_url = reverse_lazy("assets:assignment_list")


class AssetAssignmentDetailView(LoginRequiredMixin, DetailView):
    model = m.AssetAssignment
    template_name = "assets/assignment_detail.html"


class AssetAssignmentDeleteView(LoginRequiredMixin, DeleteView):
    model = m.AssetAssignment
    template_name = "confirm_delete.html"
    success_url = reverse_lazy("assets:assignment_list")


