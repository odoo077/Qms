from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from base.models import User


@receiver(m2m_changed, sender=User.companies.through)
def ensure_default_in_allowed(sender, instance: User, action, reverse, model, pk_set, **kwargs):
    """
    إذا تغيّرت قائمة الشركات المسموح بها تأكد أن الافتراضية موجودة ضمنها.
    """
    if action == "post_add" and instance.company_id:
        if not instance.companies.filter(pk=instance.company_id).exists():
            instance.companies.add(instance.company)
