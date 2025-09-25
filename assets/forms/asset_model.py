# assets/forms.py
from django import forms
from assets.models import AssetModel
from assets.widgets import KeyValueJSONWidget


class AssetModelAdminForm(forms.ModelForm):
    class Meta:
        model = AssetModel
        fields = ["active","type","name","manufacturer","sku","specs"]
        widgets = {
            "specs": KeyValueJSONWidget(),
        }
