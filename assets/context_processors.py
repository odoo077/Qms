# assets/context_processors.py
from django.utils import timezone
from datetime import timedelta
from assets.models import AssetItem, EmployeeAsset

def assets_kpis(request):
    """
    KPIs للأصول تُحقن في القوالب كلها (تُستخدم في home.html).
    تعتمد على الشركة الحالية request.company إن وُجدت.
    """
    company = getattr(request, "company", None)
    if not company:
        return {
            "kpi_assets_total": 0,
            "kpi_assets_assigned": 0,
            "kpi_assets_overdue": 0,
            "kpi_assets_warranty_soon_30": 0,
        }

    today = timezone.now().date()
    soon = today + timedelta(days=30)

    items = AssetItem.objects.filter(company=company, active=True)
    total = items.count()
    assigned = items.filter(status="assigned").count()
    overdue = EmployeeAsset.objects.filter(company=company, is_active=True, is_overdue=True).count()
    warranty_soon = items.filter(warranty_expiry__isnull=False,
                                 warranty_expiry__gte=today,
                                 warranty_expiry__lte=soon).count()

    return {
        "kpi_assets_total": total,
        "kpi_assets_assigned": assigned,
        "kpi_assets_overdue": overdue,
        "kpi_assets_warranty_soon_30": warranty_soon,
    }
