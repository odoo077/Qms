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
    """
    Read the sync fields ONLY from the Company-like object that defines
    SYNCED_WITH_PARTNER_FIELDS. Do NOT fall back to any default list.
    This effectively disables syncing identity/address fields from Partner -> Company.
    """
    return getattr(company_like, "SYNCED_WITH_PARTNER_FIELDS", ())

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
    """
    Sync name from Partner -> Company (companies only).
    Identity/address stay single-sourced on Partner.
    Guarded to avoid loops.
    """
    token = _set_guard()
    try:
        if not getattr(partner, "is_company", False) or not getattr(partner, "company_id", None):
            return
        updates = []
        p_name = getattr(partner, "name", None)
        if isinstance(p_name, str):
            p_name = p_name.strip()
        if p_name and getattr(company, "name", None) != p_name:
            company.name = p_name
            updates.append("name")
        if updates:
            company.save(update_fields=updates)
    finally:
        _reset_guard(token)


