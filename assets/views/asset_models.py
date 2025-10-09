# assets/views/asset_models.py
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from assets.models import AssetModel
from assets.forms import AssetModelForm
from .base import CompanyContextMixin, SuccessMessageMixin

class AssetModelListView(CompanyContextMixin, ListView):
    model = AssetModel
    template_name = "assets/asset_models/asset_model_list.html"
    context_object_name = "models"
    paginate_by = 20

    def get_queryset(self):
        qs = AssetModel.objects.select_related("type").order_by("type__name", "sequence", "name")
        active = self.request.GET.get("active")
        if active in {"1", "true", "True"}:
            qs = qs.filter(active=True)
        type_id = self.request.GET.get("type")
        if type_id:
            qs = qs.filter(type_id=type_id)
        return qs

class AssetModelCreateView(CompanyContextMixin, SuccessMessageMixin, CreateView):
    model = AssetModel
    form_class = AssetModelForm
    template_name = "assets/asset_models/asset_model_form.html"
    success_url = reverse_lazy("assets:asset_model_list")
    success_message = "Asset model created successfully."

class AssetModelUpdateView(CompanyContextMixin, SuccessMessageMixin, UpdateView):
    model = AssetModel
    form_class = AssetModelForm
    template_name = "assets/asset_models/asset_model_form.html"
    success_url = reverse_lazy("assets:asset_model_list")
    success_message = "Asset model updated successfully."

class AssetModelDeleteView(CompanyContextMixin, SuccessMessageMixin, DeleteView):
    model = AssetModel
    template_name = "assets/confirm_delete.html"
    success_url = reverse_lazy("assets:asset_model_list")
    success_message = "Asset model deleted."
