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
from django.core.exceptions import ValidationError
from django.contrib.auth.models import Group, Permission
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
    سلوك Odoo-like عند حفظ Company:
      1) توليد بطاقة Partner للشركة إن لم تكن موجودة — في مكان واحد وبعد commit.
      2) ضمان وجود Partner للأب إن كان محددًا.
      3) محاذاة الشجرة: Partner(child).parent = Partner(parent) (فقط عندما يكون Company.parent مضبوطًا).
      4) إعادة محاذاة Company.parent ليتبع:
            (أولوية) Partner(child).parent.company  ← إن وُجد
            (بديل)   Partner(parent).company       ← من Company.parent إن لم يوجد الأول
      5) مزامنة الاسم Company -> Partner.
    """

    # 0) لا نفعل شيئًا إذا كنا داخل تزامن داخلي
    if SYNC_IN_PROGRESS.get():
        return

    # 00) تجاهل تحديثات مسار المواد parent_path فقط (تحسين)
    update_fields = kwargs.get("update_fields")
    if update_fields and set(update_fields) == {"parent_path"}:
        return

    from django.apps import apps
    PartnerModel = apps.get_model("base", "Partner")
    CompanyModel = apps.get_model("base", "Company")

    # نفّذ المزامنة الثقيلة بعد اكتمال المعاملة لضمان قراءة/كتابة متسقة
    def _sync_after_commit(company_pk: int):
        # اجلب الشركة + الأب + شركائهم بقراءة طازجة
        comp = (
            CompanyModel.objects
            .select_related("partner", "parent", "parent__partner", "partner__parent", "partner__parent__company")
            .get(pk=company_pk)
        )

        # (A) توليد Partner للشركة إن لم يوجد — المكان الرسمي الوحيد
        if not comp.partner_id:
            parent_partner = comp.parent.partner if (comp.parent_id and getattr(comp.parent, "partner_id", None)) else None
            p = PartnerModel.objects.create(
                name=comp.name,
                company=comp,
                is_company=True,
                company_type="company",
                type="contact",
                parent=parent_partner,
            )
            comp.partner_id = p.id
            comp.save(update_fields=["partner"])
            comp.partner = p  # حدّث النسخة المربوطة محليًا

        # (B) تأكد من وجود Partner للأب إن كان هناك أب
        parent_partner_id = getattr(comp.parent, "partner_id", None)
        if comp.parent_id and not parent_partner_id:
            pp = PartnerModel.objects.create(
                name=comp.parent.name,
                company=comp.parent,
                is_company=True,
                company_type="company",
                type="contact",
            )
            comp.parent.partner_id = pp.id
            comp.parent.save(update_fields=["partner"])
            comp.parent.partner = pp
            parent_partner_id = pp.id

        # (C) محاذاة الشجرة: Partner(child).parent = Partner(parent)
        #     نضبطها فقط عندما يكون Company.parent مضبوطًا (حتى لا نمحو Parent الموجود على Partner)
        desired_parent_partner_id_from_company = parent_partner_id if comp.parent_id else None
        if comp.partner and desired_parent_partner_id_from_company is not None:
            if comp.partner.parent_id != desired_parent_partner_id_from_company:
                token = _set_guard()
                try:
                    comp.partner.parent_id = desired_parent_partner_id_from_company
                    comp.partner.save(update_fields=["parent"])
                finally:
                    _reset_guard(token)

        # (D) **الجديد**: إعادة محاذاة Company.parent بأولوية من شجرة Partner
        #     1) إن كان لدى Partner(child) أب ⇒ خذ company لذلك الأب.
        #     2) وإلا إن كان لدى Company.parent شريك ⇒ خذ company لذلك الشريك.
        desired_parent_company_id = None

        # (D-1) من شجرة Partner (الأولوية)
        partner_parent_company_id = None
        if comp.partner_id and getattr(comp.partner, "parent_id", None):
            partner_parent_company_id = getattr(comp.partner.parent, "company_id", None)

        if partner_parent_company_id:
            desired_parent_company_id = partner_parent_company_id
        else:
            # (D-2) من شجرة Company الحالية (لو متوفرة)
            if comp.parent_id and getattr(comp.parent, "partner_id", None):
                desired_parent_company_id = getattr(comp.parent.partner, "company_id", None)

        # لا تُسقط قيمة موجودة إلى None؛ حدّث فقط إذا اختلفت القيمة
        if getattr(comp, "parent_id", None) != desired_parent_company_id:
            token = _set_guard()
            try:
                comp.parent_id = desired_parent_company_id
                comp.save(update_fields=["parent"])
            finally:
                _reset_guard(token)

        # (E) مزامنة الاسم: Company → Partner
        if comp.partner:
            sync_company_to_partner(comp, comp.partner)

    transaction.on_commit(lambda: _sync_after_commit(instance.pk))


# ======================================================================
# حماية allowed companies: لا تزل الشركة الافتراضية من المسموح بها بالغلط
# ======================================================================
@receiver(m2m_changed, sender=User.companies.through)
def prevent_removing_default_company(sender, instance: User, action, pk_set, **kwargs):
    """
    حماية Odoo-like (مع تساهل أثناء الإنشاء الأول):
      - امنع إزالة الشركة الافتراضية من allowed فقط إذا كانت موجودة فعليًا الآن ضمن المسموح بها.
    """
    if not getattr(instance, "company_id", None):
        return

    default_is_currently_allowed = instance.companies.filter(pk=instance.company_id).exists()

    # pre_remove: امنع فقط إذا كنت تزيل الافتراضية وهي موجودة فعليًا الآن
    if action == "pre_remove" and default_is_currently_allowed and instance.company_id in (pk_set or []):
        raise ValidationError("Cannot remove the default company from allowed companies.")

    # pre_clear: امنع فقط إذا كانت الافتراضية موجودة فعليًا الآن (لا تمنع أثناء الإنشاء الأول)
    if action == "pre_clear" and default_is_currently_allowed:
        raise ValidationError("Cannot clear allowed companies while a default company is set.")


@receiver(m2m_changed, sender=User.companies.through)
def ensure_default_in_allowed(sender, instance: User, action, pk_set, **kwargs):
    """
    إذا تغيّرت قائمة الشركات المسموح بها تأكد أن الافتراضية ضمنها بعد الإضافة/الإزالة.
    """
    if action in {"post_add", "post_clear", "post_remove"} and instance.company_id:
        if not instance.companies.filter(pk=instance.company_id).exists():
            instance.companies.add(instance.company)


# ==========================================================
# Partner.post_save — عندما تمثل البطاقة شركة مرتبطة بـ Company
# ==========================================================
@receiver(post_save, sender=Partner)
def partner_post_save(sender, instance: Partner, created: bool, **kwargs):
    """
    عند حفظ Partner يمثّل شركة ومرتبطًا بـ Company:

      1) Company.parent = instance.parent.company (محاذاة الشجرة بالعكس).
         *لكن لا ننزل قيمة company.parent الموجودة إلى None*:
         إذا لم يكن عند Partner.parent قيمة، نحترم اختيار المستخدم السابق على Company.
      2) مزامنة الاسم: Partner.name -> Company.name (للشركات فقط).
      3) استخدام الحارس لمنع الحلقات.
    """
    # 0) لا تفعل شيئًا لو نحن داخل سلسلة مزامنة
    if SYNC_IN_PROGRESS.get():
        return

    # 1) ينطبق فقط على بطاقات الشركات المرتبطة بكيان Company
    if not getattr(instance, "is_company", False) or not getattr(instance, "company_id", None):
        return

    company = instance.company

    # 2) مزامنة الأب: Company.parent = instance.parent.company (إن وجد)
    new_parent_company_id = None
    if getattr(instance, "parent_id", None):
        parent_partner = instance.parent

        # ✅ إضافة جديدة:
        # إذا كان Parent عبارة عن بطاقة شركة لكن بلا Company مقابلة، أنشئ Company له الآن
        if getattr(parent_partner, "is_company", False) and not getattr(parent_partner, "company_id", None):
            from django.apps import apps
            CompanyModel = apps.get_model("base", "Company")
            token = _set_guard()
            try:
                parent_company = CompanyModel.objects.create(
                    name=parent_partner.name or "Company",
                    partner=parent_partner,
                )
                # اربط بطاقة الشريك بالشركة التي أنشأناها (اتساق ثنائي الاتجاه)
                parent_partner.company_id = parent_company.id
                parent_partner.save(update_fields=["company"])
            finally:
                _reset_guard(token)

        # بعد ضمان وجود Company للأب (إن لزم)، احصل على معرّفها
        new_parent_company_id = getattr(parent_partner, "company_id", None)

    # ✳️ لا تُسقط قيمة موجودة إلى None: احترم اختيار المستخدم من نموذج الشركة
    if not (new_parent_company_id is None and getattr(company, "parent_id", None)):
        if getattr(company, "parent_id", None) != new_parent_company_id:
            token = _set_guard()
            try:
                company.parent_id = new_parent_company_id
                company.save(update_fields=["parent"])
            finally:
                _reset_guard(token)

    # 3) مزامنة الاسم: Partner.name -> Company.name
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
