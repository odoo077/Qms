# base/signals.py
# ------------------------------------------------------------
# إشعارات (Signals) Odoo-like لربط Company <-> Partner
# + تهيئة المستخدم User/UserSettings
# + حماية allowed companies
# + إنشاء مجموعات افتراضية على غرار Odoo
# + Bootstrap للشركة الرئيسية عند أول ترحيل
# ------------------------------------------------------------

from __future__ import annotations

from django.db import transaction
from django.db.models.signals import post_save, m2m_changed, post_migrate
from django.dispatch import receiver
from django.db.utils import OperationalError

# نُبقي هذه الاستيرادات لأغراض sender في الديكوريترز (لا مشكلة بها)
from base.models import Company, Partner, User, UserSettings

from base.services import (
    SYNC_IN_PROGRESS,
    _set_guard,
    _reset_guard,
    sync_partner_to_company,
    sync_company_to_partner,
)

# ============================================================
# Company.post_save — توليد/مواءمة Partner للشركة بعد commit
# ============================================================
@receiver(post_save, sender=Company)
def company_post_save(sender, instance: Company, created: bool, **kwargs):

    if SYNC_IN_PROGRESS.get():
        return

    update_fields = kwargs.get("update_fields")
    if update_fields and set(update_fields) == {"parent_path"}:
        return

    from django.apps import apps
    PartnerModel = apps.get_model("base", "Partner")
    CompanyModel = apps.get_model("base", "Company")

    def _sync_after_commit(company_pk: int):
        comp = (
            CompanyModel.objects
            .select_related(
                "partner",
                "parent",
                "parent__partner",
            )
            .get(pk=company_pk)
        )

        if not comp.partner_id:
            parent_partner = None
            if comp.parent_id and getattr(comp.parent, "partner_id", None):
                parent_partner = comp.parent.partner

            p = PartnerModel.objects.create(
                name=comp.name,
                company=comp,
                is_company=True,
                company_type="company",
                type="contact",
                parent=parent_partner,
            )

            token = _set_guard()
            try:
                comp.partner_id = p.id
                comp.save(update_fields=["partner"])
            finally:
                _reset_guard(token)

            comp.partner = p

        if comp.partner_id and comp.partner and not getattr(comp.partner, "company_id", None):
            token = _set_guard()
            try:
                comp.partner.company_id = comp.id
                comp.partner.save(update_fields=["company"])
            finally:
                _reset_guard(token)

        parent_partner_id = None
        if comp.parent_id:
            parent_partner_id = getattr(comp.parent, "partner_id", None)

            if not parent_partner_id:
                pp = PartnerModel.objects.create(
                    name=comp.parent.name,
                    company=comp.parent,
                    is_company=True,
                    company_type="company",
                    type="contact",
                )

                token = _set_guard()
                try:
                    comp.parent.partner_id = pp.id
                    comp.parent.save(update_fields=["partner"])
                finally:
                    _reset_guard(token)

                comp.parent.partner = pp
                parent_partner_id = pp.id

        if comp.partner_id and comp.partner and comp.parent_id and parent_partner_id:
            if comp.partner.parent_id != parent_partner_id:
                token = _set_guard()
                try:
                    comp.partner.parent_id = parent_partner_id
                    comp.partner.save(update_fields=["parent"])
                finally:
                    _reset_guard(token)

        if comp.partner_id and comp.partner:
            sync_company_to_partner(comp, comp.partner)

    transaction.on_commit(lambda: _sync_after_commit(instance.pk))


@receiver(m2m_changed, sender=User.companies.through)
def ensure_default_in_allowed(sender, instance: User, action, pk_set, **kwargs):
    if action in {"post_add", "post_clear", "post_remove"} and instance.company_id:
        if not instance.companies.filter(pk=instance.company_id).exists():
            instance.companies.add(instance.company)


# ==========================================================
# Partner.post_save — FINAL (Identity sync only)
# ==========================================================
@receiver(post_save, sender=Partner)
def partner_post_save(sender, instance: Partner, created: bool, **kwargs):

    if SYNC_IN_PROGRESS.get():
        return

    if not instance.is_company or not instance.company_id:
        return

    company = instance.company

    token = _set_guard()
    try:
        sync_partner_to_company(instance, company)
    finally:
        _reset_guard(token)


# ==========================================================
# User.post_save — Bootstrap شريك وإعدادات المستخدم Odoo-like
# ==========================================================
@receiver(post_save, sender=User)
def bootstrap_user(sender, instance: User, created: bool, **kwargs):

    if created and not instance.partner:
        from django.apps import apps
        PartnerModel = apps.get_model("base", "Partner")
        partner = PartnerModel.objects.create(
            name=instance.get_full_name() or (instance.email.split("@")[0] if instance.email else instance.username),
            email=instance.email or "",
            company=instance.company,
            company_type="person",
            is_company=False,
            type="contact",
            parent=(instance.company.partner if instance.company and instance.company.partner_id else None),
        )
        instance.partner = partner
        instance.save(update_fields=["partner"])

    if instance.company and not instance.companies.filter(pk=instance.company_id).exists():
        instance.companies.add(instance.company)

    settings_obj, _ = UserSettings.objects.get_or_create(user=instance)

    if not settings_obj.default_company_id:
        if instance.company_id:
            settings_obj.default_company_id = instance.company_id
            settings_obj.save(update_fields=["default_company"])
        else:
            first_allowed = instance.companies.values_list("id", flat=True).first()
            if first_allowed:
                settings_obj.default_company_id = first_allowed
                settings_obj.save(update_fields=["default_company"])

    if settings_obj.default_company_id and not instance.companies.filter(pk=settings_obj.default_company_id).exists():
        instance.companies.add(settings_obj.default_company_id)


# ==========================================================
# post_migrate — الشركة الرئيسية
# ==========================================================
@receiver(post_migrate)
def bootstrap_main_company(sender, **kwargs):

    from base.models import Company, Partner

    try:
        if not Company.objects.exists():
            partner = Partner.objects.create(
                name="Main Company",
                is_company=True,
                company_type="company",
                type="contact",
            )
            Company.objects.create(
                name="Main Company",
                partner=partner,
            )
            print("✅ Created default Main Company.")
    except OperationalError:
        pass


# ===== UserStamped: تعبئة created_by / updated_by تلقائيًا =====
from django.db.models.signals import pre_save
from django.dispatch import receiver
from .security_context import get_current_user_id

@receiver(pre_save)
def _autoset_userstamped(sender, instance, **kwargs):

    if not (hasattr(instance, "created_by_id") or hasattr(instance, "updated_by_id")):
        return

    uid = get_current_user_id()
    if not uid:
        return

    is_adding = getattr(instance._state, "adding", False)

    if is_adding and hasattr(instance, "created_by_id") and not getattr(instance, "created_by_id", None):
        instance.created_by_id = uid

    if hasattr(instance, "updated_by_id"):
        instance.updated_by_id = uid
