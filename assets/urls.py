# assets/urls.py
from django.urls import path

from .views import (
    # Asset Types
    AssetTypeListView, AssetTypeCreateView, AssetTypeUpdateView, AssetTypeDeleteView,
    # Asset Models
    AssetModelListView, AssetModelCreateView, AssetModelUpdateView, AssetModelDeleteView,
    # Asset Items
    AssetItemListView, AssetItemDetailView, AssetItemCreateView, AssetItemUpdateView, AssetItemDeleteView,
    # Employee Assets (assign/return/transfer)
    EmployeeAssetListView, EmployeeAssetAssignView, EmployeeAssetReturnView, EmployeeAssetTransferView,
)
from .views.receipts import ReceiptAssignView, ReceiptReturnView

app_name = "assets"

urlpatterns = [
    # -----------------------------
    # Asset Types
    # -----------------------------
    path("asset-types/",                 AssetTypeListView.as_view(),   name="asset_type_list"),
    path("asset-types/create/",          AssetTypeCreateView.as_view(), name="asset_type_create"),
    path("asset-types/<int:pk>/edit/",   AssetTypeUpdateView.as_view(), name="asset_type_edit"),
    path("asset-types/<int:pk>/delete/", AssetTypeDeleteView.as_view(), name="asset_type_delete"),

    # -----------------------------
    # Asset Models
    # -----------------------------
    path("asset-models/",                 AssetModelListView.as_view(),   name="asset_model_list"),
    path("asset-models/create/",          AssetModelCreateView.as_view(), name="asset_model_create"),
    path("asset-models/<int:pk>/edit/",   AssetModelUpdateView.as_view(), name="asset_model_edit"),
    path("asset-models/<int:pk>/delete/", AssetModelDeleteView.as_view(), name="asset_model_delete"),

    # -----------------------------
    # Asset Items
    # -----------------------------
    path("asset-items/",                 AssetItemListView.as_view(),   name="asset_item_list"),
    path("asset-items/create/",          AssetItemCreateView.as_view(), name="asset_item_create"),
    path("asset-items/<int:pk>/",        AssetItemDetailView.as_view(), name="asset_item_detail"),
    path("asset-items/<int:pk>/edit/",   AssetItemUpdateView.as_view(), name="asset_item_edit"),
    path("asset-items/<int:pk>/delete/", AssetItemDeleteView.as_view(), name="asset_item_delete"),

    # -----------------------------
    # Employee Assets (Assign / Return / Transfer)
    # -----------------------------
    path("employee-assets/",                  EmployeeAssetListView.as_view(),   name="employee_asset_list"),
    path("employee-assets/assign/",           EmployeeAssetAssignView.as_view(), name="employee_asset_assign"),
    path("employee-assets/<int:pk>/return/",  EmployeeAssetReturnView.as_view(), name="employee_asset_return"),
    path("employee-assets/transfer/<int:item_pk>/", EmployeeAssetTransferView.as_view(), name="employee_asset_transfer"),

    # -----------------------------
    # Receipts (PDF / HTML)
    # -----------------------------
    path("employee-assets/<int:pk>/receipt-assign/", ReceiptAssignView.as_view(), name="employee_asset_receipt_assign"),
    path("employee-assets/<int:pk>/receipt-return/", ReceiptReturnView.as_view(), name="employee_asset_receipt_return"),

]
