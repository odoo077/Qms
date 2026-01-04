# assets/urls.py
from django.urls import path
from . import views as v

app_name = "assets"

urlpatterns = [
    # Categories
    path("categories/", v.AssetCategoryListView.as_view(), name="category_list"),
    path("categories/new/", v.AssetCategoryCreateView.as_view(), name="category_create"),
    path("categories/<int:pk>/", v.AssetCategoryDetailView.as_view(), name="category_detail"),
    path("categories/<int:pk>/edit/", v.AssetCategoryUpdateView.as_view(), name="category_edit"),
    path("categories/<int:pk>/delete/", v.AssetCategoryDeleteView.as_view(), name="category_delete"),

    # Assets
    path("assets/", v.AssetListView.as_view(), name="asset_list"),
    path("assets/new/", v.AssetCreateView.as_view(), name="asset_create"),
    path("assets/<int:pk>/", v.AssetDetailView.as_view(), name="asset_detail"),
    path("assets/<int:pk>/edit/", v.AssetUpdateView.as_view(), name="asset_edit"),
    path("assets/<int:pk>/delete/", v.AssetDeleteView.as_view(), name="asset_delete"),

    # Workflow actions
    path("assets/<int:pk>/assign/", v.AssetAssignView.as_view(), name="asset_assign"),
    path("assets/<int:pk>/unassign/", v.AssetUnassignView.as_view(), name="asset_unassign"),

    # Assignment history (read-only)
    path("assignments/", v.AssetAssignmentListView.as_view(), name="assignment_list"),
    path("assignments/<int:pk>/", v.AssetAssignmentDetailView.as_view(), name="assignment_detail"),
    path("assignments/<int:pk>/delete/", v.AssetAssignmentDeleteView.as_view(), name="assignment_delete"),
]
