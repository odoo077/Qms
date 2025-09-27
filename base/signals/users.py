from django.db.models.signals import post_save
from django.dispatch import receiver
from base.models import User, Partner, UserSettings


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
            company_type="person",
            is_company=False,
            type="contact",
            parent=(instance.company.partner if instance.company and instance.company.partner_id else None),
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
