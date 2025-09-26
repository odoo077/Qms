from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView, UpdateView

from ..forms import PartnerForm
from ..models import Partner

class PartnerListView(LoginRequiredMixin, ListView):
    model = Partner
    paginate_by = 20
    template_name = "base/partner_list.html"

    def get_queryset(self):
        # لم نعد نقرأ من session. مدير CompanyOwnedMixin يطبق التصفية تلقائياً
        return super().get_queryset().order_by("name")


class PartnerCreateView(LoginRequiredMixin, CreateView):
    model = Partner
    form_class = PartnerForm
    template_name = "base/partner_form.html"
    success_url = reverse_lazy("base:partner_list")


class PartnerUpdateView(LoginRequiredMixin, UpdateView):
    model = Partner
    form_class = PartnerForm
    template_name = "base/partner_form.html"
    success_url = reverse_lazy("base:partner_list")


class PartnerDetailView(LoginRequiredMixin, DetailView):
    model = Partner
    template_name = "base/partner_detail.html"