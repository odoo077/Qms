from django.db import transaction
from django.apps import apps
from django.db.models.signals import post_migrate
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_save
from django.dispatch import receiver
from guardian.shortcuts import assign_perm
from hr.models import Employee

Employee = apps.get_model("hr", "Employee")
Partner = apps.get_model("base", "Partner")


@receiver(post_save, sender=Employee)
def ensure_employee_work_contact(sender, instance: Employee, created, **kwargs):
    """
    منطق Odoo: كل موظف يجب أن يملك work_contact.
    - لو مرتبط بـ User → استخدم partner الخاص بالمستخدم (مع ضبط الشركة).
    - وإلا أنشئ Partner تحت Partner الشركة.
    """
    if instance.work_contact_id:
        return

    def _assign(partner):
        # تأكد من الشركة
        if getattr(partner, "company_id", None) != instance.company_id and hasattr(partner, "company_id"):
            partner.company_id = instance.company_id
            partner.save(update_fields=["company"])
        # اربط وأكمل الحقول المشتقة
        instance.work_contact_id = partner.id
        updates = ["work_contact"]
        if not instance.work_email and getattr(partner, "email", ""):
            instance.work_email = partner.email; updates.append("work_email")
        if not instance.work_phone and getattr(partner, "phone", ""):
            instance.work_phone = partner.phone; updates.append("work_phone")
        instance.save(update_fields=updates)

    def _do():
        user = getattr(instance, "user", None)
        if user and getattr(user, "partner", None):
            _assign(user.partner)
            return
        # أنشئ Partner جديد للموظف تحت Partner الشركة
        company_partner = None
        try:
            company_partner = Partner.objects.filter(
                company_id=instance.company_id, is_company=True
            ).first()
        except Exception:
            pass
        p = Partner.objects.create(
            name=instance.name,
            is_company=False,
            company_id=instance.company_id,
            parent=company_partner,
            type="contact",
            company_type="person",
            employee=True,
        )
        _assign(p)

    # سجّل التنفيذ بعد نجاح الـ commit؛ وإن لم نكن داخل atomic نفذ فورًا
    try:
        transaction.on_commit(_do)
    except Exception:
        _do()

@receiver(post_save, sender=Employee)
def grant_owner_perms_employee(sender, instance, created, **kwargs):
    if created and getattr(instance, "created_by", None):
        user = instance.created_by
        assign_perm("hr.view_employee", user, instance)
        assign_perm("hr.change_employee", user, instance)
        assign_perm("hr.approve_employee", user, instance)

@receiver(post_migrate)
def ensure_hr_roles(sender, **kwargs):
    if getattr(sender, "name", None) != "hr":
        return

    GROUPS = {
        "HR Managers": [
            ("approve_employee", Employee),
            ("view_private_fields", Employee),
            ("view_employee", Employee),
            ("change_employee", Employee),
        ],
        "HR Officers": [
            ("view_employee", Employee),
        ],
    }

    for group_name, entries in GROUPS.items():
        group, _ = Group.objects.get_or_create(name=group_name)
        for codename, model in entries:
            ct = ContentType.objects.get_for_model(model)
            try:
                perm = Permission.objects.get(codename=codename, content_type=ct)
                group.permissions.add(perm)
            except Permission.DoesNotExist:
                continue
