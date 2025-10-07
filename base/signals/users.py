from django.db.models.signals import post_save
from django.dispatch import receiver
from base.models import User, Partner, UserSettings

@receiver(post_save, sender=User)
def bootstrap_user(sender, instance: User, created: bool, **kwargs):
    """
    Bootstrap Odoo-like for Users:
      - إنشاء Partner مرتبط عند الإنشاء لأول مرة.
      - ضمان أن user.company ضمن user.companies.
      - إنشاء UserSettings إن لزم.
      - احترام تفضيل المستخدم: لا نكتب فوق default_company إذا كانت محددة مسبقًا.
      - ضمان أن default_company (إن وُجدت) ضمن المسموح بها.
    """

    # 1) إنشاء Partner عند الإنشاء الأول
    if created and not instance.partner:
        partner = Partner.objects.create(
            name=instance.get_full_name() or (instance.email.split("@")[0] if instance.email else instance.username),
            email=instance.email or "",
            company=instance.company,           # يرث الملكية لتظهر بطاقة الشريك ضمن شركة المستخدم
            company_type="person",
            is_company=False,
            type="contact",
            parent=(instance.company.partner if instance.company and instance.company.partner_id else None),
        )
        instance.partner = partner
        # ملاحظة: نتجنب recursion عبر post_save بالاقتصار على تحديث حقل واحد
        instance.save(update_fields=["partner"])

    # 2) ضمّن الشركة الافتراضية ضمن الشركات المسموح بها
    if instance.company and not instance.companies.filter(pk=instance.company_id).exists():
        instance.companies.add(instance.company)

    # 3) UserSettings: أنشئ إن لم يوجد
    settings_obj, _ = UserSettings.objects.get_or_create(user=instance)

    # 4) ضبط default_company أول مرة فقط (احترام تفضيل المستخدم لاحقًا)
    # - إذا كان للمستخدم تفضيل سابق، لا نغيّره.
    # - إذا لم يكن له تفضيل:
    #     * استخدم user.company إن وُجدت
    #     * وإلا (لا توجد company لكن لديه شركات مسموح بها) خُذ أول مسموح بها كتهيئة أولية.
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
