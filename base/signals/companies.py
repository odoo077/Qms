from django.db.models.signals import post_save
from django.dispatch import receiver
from base.models import Company, Partner, User
from base.services.company_partner_sync import (
    sync_company_to_partner, SYNC_IN_PROGRESS
)


@receiver(post_save, sender=Company)
def company_post_save(sender, instance: Company, created, **kwargs):
    """
    - إنشاء Partner للشركة إن لم يوجد
    - مزامنة الحقول من الشركة إلى الشريك
    - منع الحلقة باستخدام الحارس SYNC_IN_PROGRESS
    - تخطي الإشارة عندما يكون الحفظ لتحديث parent_path فقط
    """
    # تخطّي التكرار: لو كنا داخل مزامنة، لا تفعل شيئًا
    if SYNC_IN_PROGRESS.get():
        return

    # تخطّي التحديث الناتج فقط عن parent_path
    update_fields = kwargs.get("update_fields")
    if update_fields and set(update_fields) == {"parent_path"}:
        return

    # إنشاء partner للشركة إن لم يوجد
    if not getattr(instance, "partner", None):
        p = Partner.objects.create(
            name=instance.name,
            company=instance,
            is_company=True,
            company_type="company",
            type="contact",
        )
        instance.partner = p
        instance.save(update_fields=["partner"])

    # مزامنة الحقول من الشركة إلى الشريك (آمنة مع الحارس)
    if instance.partner_id:
        sync_company_to_partner(instance, instance.partner)


@receiver(post_save, sender=Company)
def company_accept_users(sender, instance: Company, created, **kwargs):
    """
    إذا كانت الشركة تحتوي accepted_users → أدرج تلك الشركة ضمن allowed لكل مستخدم مُدرج.
    """
    if instance and instance.accepted_users.exists():
        for user in instance.accepted_users.all():
            if not user.companies.filter(pk=instance.pk).exists():
                user.companies.add(instance)
