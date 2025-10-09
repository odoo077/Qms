# hr/views/contract_types.py
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView
from django.db.models import Q

from ..models import ContractType
from ..forms import ContractTypeForm


class ContractTypeListView(LoginRequiredMixin, ListView):
    """
    عرض قائمة أنواع العقود (Contract Types)
    """
    model = ContractType
    template_name = "hr/contract_types/contract_type_list.html"
    context_object_name = "types"
    paginate_by = 20
    ordering = ("sequence", "name")

    def get_queryset(self):
        qs = ContractType.objects.order_by(*self.ordering)
        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(code__icontains=q))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = "Contract Types"
        return ctx


class ContractTypeCreateView(LoginRequiredMixin, CreateView):
    """
    إنشاء نوع عقد جديد.
    """
    model = ContractType
    form_class = ContractTypeForm
    template_name = "hr/contract_types/contract_type_form.html"
    success_url = reverse_lazy("hr:contract_type_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = "Create Contract Type"
        return ctx


class ContractTypeUpdateView(LoginRequiredMixin, UpdateView):
    """
    تعديل نوع عقد موجود.
    """
    model = ContractType
    form_class = ContractTypeForm
    template_name = "hr/contract_types/contract_type_form.html"
    success_url = reverse_lazy("hr:contract_type_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = "Edit Contract Type"
        return ctx


class ContractTypeDetailView(LoginRequiredMixin, DetailView):
    """
    عرض تفاصيل نوع العقد.
    """
    model = ContractType
    template_name = "hr/contract_types/contract_type_detail.html"
    context_object_name = "ctype"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        contract_type = self.object
        ctx["page_title"] = f"Contract Type: {contract_type.name}"
        return ctx


class ContractTypeDeleteView(LoginRequiredMixin, DeleteView):
    """
    حذف نوع عقد.
    """
    model = ContractType
    template_name = "hr/contract_types/contract_type_confirm_delete.html"
    success_url = reverse_lazy("hr:contract_type_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = "Delete Contract Type"
        return ctx
