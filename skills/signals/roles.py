from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from skills.models import HrEmployeeSkill  # عدّل الاسم حسب ملفك

@receiver(post_migrate)
def ensure_skills_roles(sender, **kwargs):
    if getattr(sender, "name", None) != "skills":
        return

    GROUPS = {
        "Skills Managers": [
            ("rate_skill", HrEmployeeSkill),
            ("view_employeeskill", HrEmployeeSkill),
            ("change_employeeskill", HrEmployeeSkill),
        ],
        "Skills Officers": [
            ("view_employeeskill", HrEmployeeSkill),
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
