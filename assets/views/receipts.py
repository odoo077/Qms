# assets/views/receipts.py
from django.shortcuts import get_object_or_404
from django.views import View
from django.utils import timezone
from django.contrib.auth.mixins import LoginRequiredMixin

from assets.models import EmployeeAsset
from assets.services.pdf import render_receipt_pdf
from assets.views.base import CompanyContextMixin
from base.security import ObjectActionPermissionMixin


class ReceiptAssignView(
    ObjectActionPermissionMixin, CompanyContextMixin, LoginRequiredMixin, View
):
    required_perm_app = "assets"
    required_perm_codename = "assign_item"

    def get(self, request, pk):
        record = get_object_or_404(EmployeeAsset.objects.select_related("employee", "item"), pk=pk)
        self.check_perm(record)
        context = {
            "record": record,
            "company": record.company,
            "employee": record.employee,
            "item": record.item,
            "today": timezone.now().date(),
            "receipt_type": "assign",
            "title": "Asset Assignment Receipt",
        }
        return render_receipt_pdf(request, "assets/employee_assets/receipt_assign.html", context, "assign-receipt")


class ReceiptReturnView(
    ObjectActionPermissionMixin, CompanyContextMixin, LoginRequiredMixin, View
):
    required_perm_app = "assets"
    required_perm_codename = "return_item"

    def get(self, request, pk):
        record = get_object_or_404(EmployeeAsset.objects.select_related("employee", "item"), pk=pk)
        self.check_perm(record)
        context = {
            "record": record,
            "company": record.company,
            "employee": record.employee,
            "item": record.item,
            "today": timezone.now().date(),
            "receipt_type": "return",
            "title": "Asset Return Receipt",
        }
        return render_receipt_pdf(request, "assets/employee_assets/receipt_return.html", context, "return-receipt")
