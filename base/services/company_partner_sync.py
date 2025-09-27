# base/services/company_partner_sync.py
from typing import Iterable, List
from contextvars import ContextVar
from django.db import transaction

# حارس منع التداخل بين إشعارات الحفظ
SYNC_IN_PROGRESS: ContextVar[bool] = ContextVar("SYNC_IN_PROGRESS", default=False)

def _set_guard():
    token = SYNC_IN_PROGRESS.set(True)
    return token

def _reset_guard(token):
    SYNC_IN_PROGRESS.reset(token)

def _get_sync_fields(company_like) -> Iterable[str]:
    default = (
        "name", "email", "phone", "website",
        "street", "street2", "city", "state", "zip", "country",
        "vat", "company_registry",
    )
    # إن وُجدت قائمة على الكيان (Company) نستخدمها، وإلا الافتراضي
    return getattr(company_like, "SYNCED_WITH_PARTNER_FIELDS", default)

def _collect_changes(src, dst) -> List[str]:
    updates: List[str] = []
    for f in _get_sync_fields(src):
        if hasattr(src, f) and hasattr(dst, f):
            v = getattr(src, f, None)
            if isinstance(v, str):
                nv = v.strip()
            else:
                nv = v
            if getattr(dst, f, None) != nv:
                setattr(dst, f, nv)
                updates.append(f)
    return updates


@transaction.atomic
def sync_company_to_partner(company, partner):
    token = _set_guard()
    try:
        updates = _collect_changes(company, partner)
        # enforced flags على الـ partner الخاص بالشركة
        force = False
        if getattr(partner, "is_company", False) is not True:
            partner.is_company = True
            force = True
        if getattr(partner, "company_type", "") != "company":
            partner.company_type = "company"
            force = True
        if getattr(partner, "type", "") != "contact":
            partner.type = "contact"
            force = True
        # تأكد من ربط نفس الشركة
        if hasattr(partner, "company") and partner.company_id != company.id:
            partner.company = company
            force = True
        if force:
            # لو غيّرنا أعلاه، لا تنس إضافتها إلى update_fields
            for f in ("is_company", "company_type", "type", "company"):
                if f not in updates:
                    updates.append(f)
        if updates:
            partner.save(update_fields=updates)
    finally:
        _reset_guard(token)

@transaction.atomic
def sync_partner_to_company(partner, company):
    token = _set_guard()
    try:
        updates = _collect_changes(partner, company)
        if updates:
            company.save(update_fields=updates)
    finally:
        _reset_guard(token)
