# assets/forms/__init__.py
from .base import TailwindFormMixin, CompanyScopedFormMixin
from .asset_type_form import AssetTypeForm
from .asset_model_form import AssetModelForm
from .asset_item_form import AssetItemForm
from .employee_asset_form import (
    EmployeeAssetAssignForm,
    EmployeeAssetReturnForm,
    EmployeeAssetTransferForm,
)

__all__ = [
    "TailwindFormMixin",
    "CompanyScopedFormMixin",
    "AssetTypeForm",
    "AssetModelForm",
    "AssetItemForm",
    "EmployeeAssetAssignForm",
    "EmployeeAssetReturnForm",
    "EmployeeAssetTransferForm",
]
