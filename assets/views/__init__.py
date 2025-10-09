# assets/views/__init__.py
from .asset_types import (
    AssetTypeListView, AssetTypeCreateView, AssetTypeUpdateView, AssetTypeDeleteView
)
from .asset_models import (
    AssetModelListView, AssetModelCreateView, AssetModelUpdateView, AssetModelDeleteView
)
from .asset_items import (
    AssetItemListView, AssetItemDetailView, AssetItemCreateView, AssetItemUpdateView, AssetItemDeleteView
)
from .employee_assets import (
    EmployeeAssetListView, EmployeeAssetAssignView, EmployeeAssetReturnView, EmployeeAssetTransferView
)
from .receipts import (
    ReceiptAssignView, ReceiptReturnView
)
