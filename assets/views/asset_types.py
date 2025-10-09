# assets/views/asset_types.py
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from assets.models import AssetType
from assets.forms import AssetTypeForm
from .base import CompanyContextMixin, SuccessMessageMixin

class AssetTypeListView(CompanyContextMixin, ListView):
    model = AssetType
    template_name = "assets/asset_types/asset_type_list.html"
    context_object_name = "types"
    paginate_by = 20

    def get_queryset(self):
        qs = AssetType.objects.all().order_by("name")
        active = self.request.GET.get("active")
        if active in {"1", "true", "True"}:
            qs = qs.filter(active=True)
        return qs

class AssetTypeCreateView(CompanyContextMixin, SuccessMessageMixin, CreateView):
    model = AssetType
    form_class = AssetTypeForm
    template_name = "assets/asset_types/asset_type_form.html"
    success_url = reverse_lazy("assets:asset_type_list")
    success_message = "Asset type created successfully."

class AssetTypeUpdateView(CompanyContextMixin, SuccessMessageMixin, UpdateView):
    model = AssetType
    form_class = AssetTypeForm
    template_name = "assets/asset_types/asset_type_form.html"
    success_url = reverse_lazy("assets:asset_type_list")
    success_message = "Asset type updated successfully."

class AssetTypeDeleteView(CompanyContextMixin, SuccessMessageMixin, DeleteView):
    model = AssetType
    template_name = "assets/confirm_delete.html"
    success_url = reverse_lazy("assets:asset_type_list")
    success_message = "Asset type deleted."
