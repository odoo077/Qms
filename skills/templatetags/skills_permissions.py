# skills/templatetags/skills_permissions.py
from django import template

register = template.Library()

# ------------------------------------------------------------
# Generic permission helpers (same concept as assets)
# ------------------------------------------------------------

def _can_add(user, perm):
    return user.has_perm(f"skills.{perm}")

def _can_edit(user, perm, obj):
    if user.has_perm(f"skills.{perm}"):
        return True
    # Object-level ACL (if using guardian/ACLManager)
    if hasattr(obj, "user_can_edit"):
        return obj.user_can_edit(user)
    return False

def _can_view(user, perm, obj):
    if user.has_perm(f"skills.{perm}"):
        return True
    if hasattr(obj, "user_can_view"):
        return obj.user_can_view(user)
    return False

def _can_delete(user, perm, obj):
    if user.is_superuser:
        return True
    if user.has_perm(f"skills.{perm}"):
        return True
    if hasattr(obj, "user_can_delete"):
        return obj.user_can_delete(user)
    return False


# ------------------------------------------------------------
# SkillType permissions
# ------------------------------------------------------------
@register.simple_tag
def can_add_skilltype(user):
    return _can_add(user, "add_skilltype")

@register.simple_tag
def can_edit_skilltype(user, obj):
    return _can_edit(user, "change_skilltype", obj)

@register.simple_tag
def can_view_skilltype(user, obj):
    return _can_view(user, "view_skilltype", obj)

@register.simple_tag
def can_delete_skilltype(user, obj):
    return _can_delete(user, "delete_skilltype", obj)


# ------------------------------------------------------------
# SkillLevel permissions
# ------------------------------------------------------------
@register.simple_tag
def can_add_skilllevel(user):
    return _can_add(user, "add_skilllevel")

@register.simple_tag
def can_edit_skilllevel(user, obj):
    return _can_edit(user, "change_skilllevel", obj)

@register.simple_tag
def can_view_skilllevel(user, obj):
    return _can_view(user, "view_skilllevel", obj)

@register.simple_tag
def can_delete_skilllevel(user, obj):
    return _can_delete(user, "delete_skilllevel", obj)


# ------------------------------------------------------------
# Skill permissions
# ------------------------------------------------------------
@register.simple_tag
def can_add_skill(user):
    return _can_add(user, "add_skill")

@register.simple_tag
def can_edit_skill(user, obj):
    return _can_edit(user, "change_skill", obj)

@register.simple_tag
def can_view_skill(user, obj):
    return _can_view(user, "view_skill", obj)

@register.simple_tag
def can_delete_skill(user, obj):
    return _can_delete(user, "delete_skill", obj)


# ------------------------------------------------------------
# EmployeeSkill permissions
# ------------------------------------------------------------
@register.simple_tag
def can_add_employeeskill(user):
    return _can_add(user, "add_employeeskill")

@register.simple_tag
def can_edit_employeeskill(user, obj):
    return _can_edit(user, "change_employeeskill", obj)

@register.simple_tag
def can_view_employeeskill(user, obj):
    return _can_view(user, "view_employeeskill", obj)

@register.simple_tag
def can_delete_employeeskill(user, obj):
    return _can_delete(user, "delete_employeeskill", obj)


# ------------------------------------------------------------
# ResumeLineType permissions
# ------------------------------------------------------------
@register.simple_tag
def can_add_resumelinetype(user):
    return _can_add(user, "add_resumelinetype")

@register.simple_tag
def can_edit_resumelinetype(user, obj):
    return _can_edit(user, "change_resumelinetype", obj)

@register.simple_tag
def can_view_resumelinetype(user, obj):
    return _can_view(user, "view_resumelinetype", obj)

@register.simple_tag
def can_delete_resumelinetype(user, obj):
    return _can_delete(user, "delete_resumelinetype", obj)


# ------------------------------------------------------------
# ResumeLine permissions
# ------------------------------------------------------------
@register.simple_tag
def can_add_resumeline(user):
    return _can_add(user, "add_resumeline")

@register.simple_tag
def can_edit_resumeline(user, obj):
    return _can_edit(user, "change_resumeline", obj)

@register.simple_tag
def can_view_resumeline(user, obj):
    return _can_view(user, "view_resumeline", obj)

@register.simple_tag
def can_delete_resumeline(user, obj):
    return _can_delete(user, "delete_resumeline", obj)
