from django.db.models.signals import post_save
from django.dispatch import receiver
from base.models import Partner
from base.services.company_partner_sync import (
    sync_partner_to_company, SYNC_IN_PROGRESS
)


@receiver(post_save, sender=Partner)
def partner_post_save(sender, instance: Partner, created, **kwargs):
    """
    إذا كان هذا هو Partner الخاص بالشركة → اعكس بعض الحقول إلى Company
    مع منع الحلقة باستخدام الحارس.
    """
    if SYNC_IN_PROGRESS.get():
        return

    company = getattr(instance, "company", None)
    if company and getattr(company, "partner_id", None) == instance.id:
        # انعكاس انتقائي (يتم داخليًا في الخدمة)
        sync_partner_to_company(instance, company)
