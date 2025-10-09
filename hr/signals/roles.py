from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from hr.models import Employee

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
