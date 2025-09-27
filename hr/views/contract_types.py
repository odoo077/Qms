# hr/views/contract_types.py
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView
from ..models import ContractType
from ..forms import ContractTypeForm

class ContractTypeListView(LoginRequiredMixin, ListView):
    model = ContractType
    template_name = "hr/contract_types/contract_type_list.html"
    context_object_name = "types"
    paginate_by = 20
    ordering = ("sequence", "name")

    def get_queryset(self):
        qs = super().get_queryset().order_by(*self.ordering)
        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(name__icontains=q) | qs.filter(code__icontains=q)
        return qs

class ContractTypeCreateView(LoginRequiredMixin, CreateView):
    model = ContractType
    form_class = ContractTypeForm
    template_name = "hr/contract_types/contract_type_form.html"
    success_url = reverse_lazy("hr:contract_type_list")

class ContractTypeUpdateView(LoginRequiredMixin, UpdateView):
    model = ContractType
    form_class = ContractTypeForm
    template_name = "hr/contract_types/contract_type_form.html"
    success_url = reverse_lazy("hr:contract_type_list")

class ContractTypeDetailView(LoginRequiredMixin, DetailView):
    model = ContractType
    template_name = "hr/contract_types/contract_type_detail.html"
    context_object_name = "ctype"

class ContractTypeDeleteView(LoginRequiredMixin, DeleteView):
    model = ContractType
    template_name = "hr/contract_types/contract_type_confirm_delete.html"
    success_url = reverse_lazy("hr:contract_type_list")
