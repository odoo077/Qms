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
    sync_partner_to_company,   # مزامنة الاسم من Partner -> Company
    sync_company_to_partner,   # مزامنة الاسم من Company -> Partner
)

# ============================================================
# Company.post_save — توليد/مواءمة Partner للشركة بعد commit
# ============================================================
@receiver(post_save, sender=Company)
def company_post_save(sender, instance: Company, created: bool, **kwargs):
    """
    سلوك Odoo-like عند حفظ Company (وفق المنطق المتفق عليه):

    1) توليد Partner للشركة إن لم تكن موجودة (بعد commit).
    2) ضمان وجود Partner للأب إن كان Company.parent محددًا.
    3) محاذاة شجرة Partner فقط بناءً على Company.parent:
          Partner(child).parent = Partner(parent)
       (لكن لا نعدّل Company.parent بناءً على Partner هنا)
    4) مزامنة الاسم Company -> Partner.

    ملاحظة مهمة:
    - لا يوجد هنا أي منطق يعيد ضبط Company.parent من Partner.
      (اتجاه Parent من Partner -> Company يكون في partner_post_save فقط)
    """

    # 0) لا نفعل شيئًا إذا كنا داخل تزامن داخلي
    if SYNC_IN_PROGRESS.get():
        return

    # 00) تجاهل تحديثات parent_path فقط (تحسين)
    update_fields = kwargs.get("update_fields")
    if update_fields and set(update_fields) == {"parent_path"}:
        return

    from django.apps import apps
    PartnerModel = apps.get_model("base", "Partner")
    CompanyModel = apps.get_model("base", "Company")

    def _sync_after_commit(company_pk: int):
        # قراءة طازجة + علاقات كافية
        comp = (
            CompanyModel.objects
            .select_related(
                "partner",
                "parent",
                "parent__partner",
            )
            .get(pk=company_pk)
        )

        # ----------------------------------------------------
        # (A) أنشئ Partner للشركة إن لم يوجد — المكان الرسمي الوحيد
        # ----------------------------------------------------
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

            comp.partner = p  # تحديث النسخة المحلية

        # ----------------------------------------------------
        # (A.1) إن كان Partner موجودًا مسبقًا لكنه غير مربوط بـ Company → اربطه الآن
        # ----------------------------------------------------
        if comp.partner_id and comp.partner and not getattr(comp.partner, "company_id", None):
            token = _set_guard()
            try:
                comp.partner.company_id = comp.id
                comp.partner.save(update_fields=["company"])
            finally:
                _reset_guard(token)

        # ----------------------------------------------------
        # (B) تأكد من وجود Partner للأب إن كان هناك Company.parent
        # ----------------------------------------------------
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

        # ----------------------------------------------------
        # (C) محاذاة شجرة Partner من Company فقط:
        #     Partner(child).parent = Partner(parent) عندما يكون Company.parent موجودًا
        # ----------------------------------------------------
        if comp.partner_id and comp.partner and comp.parent_id and parent_partner_id:
            if comp.partner.parent_id != parent_partner_id:
                token = _set_guard()
                try:
                    comp.partner.parent_id = parent_partner_id
                    comp.partner.save(update_fields=["parent"])
                finally:
                    _reset_guard(token)

        # ----------------------------------------------------
        # (E) مزامنة الاسم: Company → Partner
        # ----------------------------------------------------
        if comp.partner_id and comp.partner:
            sync_company_to_partner(comp, comp.partner)

    transaction.on_commit(lambda: _sync_after_commit(instance.pk))


@receiver(m2m_changed, sender=User.companies.through)
def ensure_default_in_allowed(sender, instance: User, action, pk_set, **kwargs):
    """
    إذا تغيّرت قائمة الشركات المسموح بها تأكد أن الافتراضية ضمنها بعد الإضافة/الإزالة.
    """
    if action in {"post_add", "post_clear", "post_remove"} and instance.company_id:
        if not instance.companies.filter(pk=instance.company_id).exists():
            instance.companies.add(instance.company)


# ==========================================================
# Partner.post_save — FINAL (Identity sync only)
# ==========================================================
@receiver(post_save, sender=Partner)
def partner_post_save(sender, instance: Partner, created: bool, **kwargs):
    """
    FINAL Partner post-save logic (Best Practice):

    - Company is the SINGLE source of truth for hierarchy.
    - Partner MUST NOT modify Company.parent.
    - This signal ONLY syncs identity fields (e.g. name).
    - No hierarchy creation, no parent propagation, no company creation.
    """

    # --------------------------------------------------
    # 0) Prevent recursive sync loops
    # --------------------------------------------------
    if SYNC_IN_PROGRESS.get():
        return

    # --------------------------------------------------
    # 1) Apply ONLY for company partners linked to Company
    # --------------------------------------------------
    if not instance.is_company or not instance.company_id:
        return

    company = instance.company

    # --------------------------------------------------
    # 2) Identity sync ONLY (Partner → Company)
    # --------------------------------------------------
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
    """
    Bootstrap للمستخدم:
      - إنشاء Partner مرتبط عند الإنشاء لأول مرة (بطاقة شخص).
      - ضمان أن user.company ضمن user.companies.
      - إنشاء UserSettings إن لزم.
      - احترام تفضيل المستخدم (لا نكتب فوق default_company إن كانت محددة).
      - ضمان أن default_company ضمن المسموح بها.
    """
    # 1) إنشاء Partner للشخص عند الإنشاء الأول
    if created and not instance.partner:
        from django.apps import apps
        PartnerModel = apps.get_model("base", "Partner")
        partner = PartnerModel.objects.create(
            name=instance.get_full_name() or (instance.email.split("@")[0] if instance.email else instance.username),
            email=instance.email or "",
            company=instance.company,  # الملكية تبعًا لشركة المستخدم
            company_type="person",
            is_company=False,
            type="contact",
            parent=(instance.company.partner if instance.company and instance.company.partner_id else None),
        )
        instance.partner = partner
        instance.save(update_fields=["partner"])

    # 2) ضمّن الشركة الافتراضية ضمن المسموح بها (Odoo-like)
    if instance.company and not instance.companies.filter(pk=instance.company_id).exists():
        instance.companies.add(instance.company)

    # 3) UserSettings: أنشئ إن لم يوجد
    settings_obj, _ = UserSettings.objects.get_or_create(user=instance)

    # 4) ضبط default_company أول مرة فقط
    if not settings_obj.default_company_id:
        if instance.company_id:
            settings_obj.default_company_id = instance.company_id
            settings_obj.save(update_fields=["default_company"])
        else:
            first_allowed = instance.companies.values_list("id", flat=True).first()
            if first_allowed:
                settings_obj.default_company_id = first_allowed
                settings_obj.save(update_fields=["default_company"])

    # 5) تأكد أن default_company ضمن المسموح بها دائمًا
    if settings_obj.default_company_id and not instance.companies.filter(pk=settings_obj.default_company_id).exists():
        instance.companies.add(settings_obj.default_company_id)


# ==========================================================
# post_migrate — الشركة الرئيسية
# ==========================================================

@receiver(post_migrate)
def bootstrap_main_company(sender, **kwargs):
    """
    إنشاء الشركة الرئيسية (Main Company) عند أول تشغيل النظام إذا لم توجد أي شركة.
    تشبه "My Company" في Odoo.
    """
    from base.models import Company, Partner

    try:
        if not Company.objects.exists():
            # 1) أنشئ الشريك أولاً
            partner = Partner.objects.create(
                name="Main Company",
                is_company=True,
                company_type="company",
                type="contact",
            )
            # 2) أنشئ الشركة الرئيسية
            Company.objects.create(
                name="Main Company",
                partner=partner,
            )
            print("✅ Created default Main Company.")
    except OperationalError:
        # أثناء عمليات الترحيل الأولى قد لا تكون الجداول جاهزة بعد
        pass


# ===== UserStamped: تعبئة created_by / updated_by تلقائيًا =====
from django.db.models.signals import pre_save
from django.dispatch import receiver
from .security_context import get_current_user_id

@receiver(pre_save)
def _autoset_userstamped(sender, instance, **kwargs):
    """
    يعمَل لأي موديل يحتوي حقلي created_by / updated_by.
    - عند الإنشاء: يضبط created_by إذا كان فارغًا + يضبط دائمًا updated_by.
    - عند التعديل: يضبط دائمًا updated_by.
    """
    # لا نفعل شيئًا إن لم يملك الحقول
    if not (hasattr(instance, "created_by_id") or hasattr(instance, "updated_by_id")):
        return

    uid = get_current_user_id()
    if not uid:
        return  # لا يوجد مستخدم في السياق (سكربت/مهاجرات/سيرفس)

    # إضافة أم تعديل؟
    is_adding = getattr(instance._state, "adding", False)

    if is_adding and hasattr(instance, "created_by_id") and not getattr(instance, "created_by_id", None):
        instance.created_by_id = uid

    if hasattr(instance, "updated_by_id"):
        instance.updated_by_id = uid

# ==========================================================
# Default ACL for base objects (Company / Partner)
# ==========================================================
from base.acl_service import apply_default_acl

@receiver(post_save, sender=Partner)
def _partner_default_acl(sender, instance, created, **kwargs):
    """يطبّق الصلاحيات الافتراضية عند إنشاء Partner جديد."""
    if created:
        apply_default_acl(instance)

@receiver(post_save, sender=Company)
def _company_default_acl(sender, instance, created, **kwargs):
    """يطبّق الصلاحيات الافتراضية عند إنشاء Company جديدة."""
    if created:
        apply_default_acl(instance)

@receiver(post_save, sender=User)
def _user_default_acl(sender, instance, created, **kwargs):
    if created:
        apply_default_acl(instance)
