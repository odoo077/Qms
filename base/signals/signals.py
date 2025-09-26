# base/signals/signals.py
from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver

from ..models import User, Partner, Company, UserSettings

@receiver(post_save, sender=User)
def bootstrap_user(sender, instance: User, created, **kwargs):
    """
    - إنشاء Partner تلقائيًا إن لم يوجد (Odoo-esque)
    - ضمان إدراج الشركة الافتراضية ضمن الشركات المسموحة
    - إنشاء UserSettings وضبط default_company = company عند أول مرة
    """
    # 1) Partner
    if created and not instance.partner:
        partner = Partner.objects.create(
            name=instance.get_full_name() or instance.email.split("@")[0],
            email=instance.email,
            company=instance.company,
        )
        instance.partner = partner
        instance.save(update_fields=["partner"])

    # 2) allowed companies تحتوي الافتراضية
    if instance.company and not instance.companies.filter(pk=instance.company_id).exists():
        instance.companies.add(instance.company)

    # 3) UserSettings
    settings_obj, _ = UserSettings.objects.get_or_create(user=instance)
    if instance.company and not settings_obj.default_company:
        settings_obj.default_company = instance.company
        settings_obj.save(update_fields=["default_company"])


@receiver(m2m_changed, sender=User.companies.through)
def ensure_default_in_allowed(sender, instance: User, action, reverse, model, pk_set, **kwargs):
    """
    إذا تغيّرت قائمة الشركات المسموح بها تأكد أن الافتراضية موجودة ضمنها.
    """
    if action == "post_add" and instance.company_id:
        if not instance.companies.filter(pk=instance.company_id).exists():
            instance.companies.add(instance.company)


@receiver(post_save, sender=Company)
def company_accept_users(sender, instance: Company, created, **kwargs):
    """
    إذا كانت الشركة تحتوي accepted_users → أدرج تلك الشركة ضمن allowed لكل مستخدم مُدرج.
    """
    if instance and instance.accepted_users.exists():
        for user in instance.accepted_users.all():
            if not user.companies.filter(pk=instance.pk).exists():
                user.companies.add(instance)


@receiver(post_save, sender=Company)
def ensure_company_partner(sender, instance: Company, created, **kwargs):
    """
    أنشئ Partner يمثل الشركة إن لم يوجد،
    وقم بمزامنة الحقول الأساسية عند كل حفظ.
    """
    # 1) الإنشاء عند أول مرة
    if created and not instance.partner:
        p = Partner.objects.create(
            name=instance.name,
            is_company=True,
            company_type="company",
            type="contact",
            parent=None,
            company=instance,            # يربط الشريك بهذه الشركة كمالك سياقي
            email=instance.email or "",
            phone=instance.phone or "",
            website=instance.website or "",
            vat=instance.vat or "",
            company_registry=instance.company_registry or "",
            street=instance.street,
            street2=instance.street2,
            zip=instance.zip,
            city=instance.city,
            state=instance.state,
            country=instance.country,
        )
        instance.partner = p
        instance.save(update_fields=["partner"])
        return

    # 2) المزامنة عند التعديل (إن كان هناك Partner مرتبط)
    if instance.partner:
        p = instance.partner
        changed = False

        for f_comp, f_part in [
            ("name", "name"),
            ("email", "email"),
            ("phone", "phone"),
            ("website", "website"),
            ("vat", "vat"),
            ("company_registry", "company_registry"),
            ("street", "street"),
            ("street2", "street2"),
            ("zip", "zip"),
            ("city", "city"),
            ("state", "state"),
            ("country", "country"),
        ]:
            v = getattr(instance, f_comp)
            if getattr(p, f_part) != v:
                setattr(p, f_part, v)
                changed = True

        # ضمّن سمات الهوية
        if not p.is_company or p.company_type != "company":
            p.is_company = True
            p.company_type = "company"
            changed = True

        # اربط السياق بالشركة إن لم يكن مضبوطًا
        if p.company_id != instance.id:
            p.company = instance
            changed = True

        if changed:
            p.save()