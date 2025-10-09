# assets/services/pdf.py
from django.http import HttpResponse
from django.template.loader import get_template
from django.utils import timezone

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
