from django.db import transaction
from django.core.exceptions import ValidationError
from assets.models import EmployeeAsset, AssetItem
from django.http import HttpResponse
from django.template.loader import get_template
from django.utils import timezone


class AssignmentService:

    @staticmethod
    @transaction.atomic
    def assign_item(item: AssetItem, employee, date_assigned=None, due_back=None, note=""):
        if item.status in {"lost", "scrapped"}:
            raise ValidationError("Cannot assign lost or scrapped items.")
        if EmployeeAsset.objects.filter(item=item, is_active=True).exists():
            raise ValidationError("This item is already assigned.")
        rec = EmployeeAsset.objects.create(
            employee=employee,
            item=item,
            date_assigned=date_assigned or timezone.now().date(),
            due_back=due_back,
            handover_note=note,
        )
        return rec

    @staticmethod
    @transaction.atomic
    def return_item(assignment: EmployeeAsset, date_returned=None, note=""):
        if not assignment.is_active:
            return assignment
        assignment.mark_returned(date_returned=date_returned, return_note=note)
        return assignment

    @staticmethod
    @transaction.atomic
    def transfer_item(item: AssetItem, to_employee, date_assigned=None, due_back=None, note=""):
        # إرجاع التسليم الحالي ثم إنشاء تسليم جديد
        curr = EmployeeAsset.objects.filter(item=item, is_active=True).first()
        if curr:
            AssignmentService.return_item(curr, date_returned=date_assigned or timezone.now().date(), note="Auto-transfer")
        return AssignmentService.assign_item(item, to_employee, date_assigned=date_assigned, due_back=due_back, note=note)

# ---------- pdf services -------

"""
MSYS2 is a collection of tools and libraries providing you with an easy-to-use environment for building,
 installing and running native Windows software.
 مكتبة weasyprint تتطلب تنصيب مكتبات على النظام الاصلي ( خاصة مع نظام وندوز ) لذلك نحتاج ل MSYS2
"""
try:
    from weasyprint import HTML
    WEASY_AVAILABLE = True
except ImportError:
    WEASY_AVAILABLE = False


def render_receipt_pdf(request, template_name, context, filename_prefix="receipt"):
    """
    تُحوّل قالب HTML إلى PDF باستخدام WeasyPrint.
    إن لم تتوفر المكتبة، تُرجع صفحة HTML للطباعة.
    """
    template = get_template(template_name)
    html = template.render(context)

    # إذا المستخدم طلب صراحة HTML
    if request.GET.get("format") == "html" or not WEASY_AVAILABLE:
        return HttpResponse(html)

    # إنشاء PDF
    pdf_file = HTML(string=html, base_url=request.build_absolute_uri()).write_pdf()
    response = HttpResponse(pdf_file, content_type="application/pdf")
    ts = timezone.now().strftime("%Y%m%d-%H%M%S")
    response["Content-Disposition"] = f'inline; filename="{filename_prefix}-{ts}.pdf"'
    return response
