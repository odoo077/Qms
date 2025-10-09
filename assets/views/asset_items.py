# assets/views/asset_items.py
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from assets.models import AssetItem
from assets.forms import AssetItemForm
from .base import CompanyContextMixin, SuccessMessageMixin

class AssetItemListView(CompanyContextMixin, ListView):
    model = AssetItem
    template_name = "assets/asset_items/asset_item_list.html"
    context_object_name = "items"
    paginate_by = 25

    def get_queryset(self):
        qs = AssetItem.objects.select_related("model", "model__type", "current_employee").order_by(
            "model__type__name", "model__name", "asset_tag"
        )
        if self.company:
            qs = qs.filter(company=self.company)
        status = self.request.GET.get("status")
        if status:
            qs = qs.filter(status=status)
        search = self.request.GET.get("q")
        if search:
            qs = qs.filter(asset_tag__icontains=search) | qs.filter(serial_no__icontains=search)
        return qs

class AssetItemDetailView(CompanyContextMixin, DetailView):
    model = AssetItem
    template_name = "assets/asset_items/asset_item_detail.html"
    context_object_name = "item"

    def get_queryset(self):
        qs = super().get_queryset().select_related("model", "model__type", "current_employee")
        if self.company:
            qs = qs.filter(company=self.company)
        return qs

class AssetItemCreateView(CompanyContextMixin, SuccessMessageMixin, CreateView):
    model = AssetItem
    form_class = AssetItemForm
    template_name = "assets/asset_items/asset_item_form.html"
    success_message = "Asset item created successfully."

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["company"] = self.company
        return kwargs

    def get_success_url(self):
        return reverse_lazy("assets:asset_item_list")

class AssetItemUpdateView(CompanyContextMixin, SuccessMessageMixin, UpdateView):
    model = AssetItem
    form_class = AssetItemForm
    template_name = "assets/asset_items/asset_item_form.html"
    success_message = "Asset item updated successfully."

    def get_queryset(self):
        qs = super().get_queryset()
        if self.company:
            qs = qs.filter(company=self.company)
        return qs

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["company"] = self.company
        return kwargs

    def get_success_url(self):
        return reverse_lazy("assets:asset_item_list")

class AssetItemDeleteView(CompanyContextMixin, SuccessMessageMixin, DeleteView):
    model = AssetItem
    template_name = "assets/confirm_delete.html"
    success_url = reverse_lazy("assets:asset_item_list")

    def get_queryset(self):
        qs = super().get_queryset()
        if self.company:
            qs = qs.filter(company=self.company)
        return qs
