# base/acl_service.py
from __future__ import annotations
from django.contrib.contenttypes.models import ContentType
from .acl import ObjectACL

def grant_access(obj, *, user=None, group=None, view=True, change=False, delete=False, active=True, company=None):
    """
    امنح/حدّث ACE على سجل.
    """
    ct = ContentType.objects.get_for_model(obj, for_concrete_model=False)
    return ObjectACL.objects.update_or_create(
        content_type=ct, object_id=obj.pk, user=user, group=group,
        defaults=dict(can_view=view, can_change=change, can_delete=delete, active=active, company=company),
    )[0]

def revoke_access(obj, *, user=None, group=None):
    """
    ألغِ ACE الخاص بالمستخدم/المجموعة على السجل.
    """
    ct = ContentType.objects.get_for_model(obj, for_concrete_model=False)
    return ObjectACL.objects.filter(content_type=ct, object_id=obj.pk, user=user, group=group).delete()

def list_access(obj):
    """
    أعِد جميع ACEs على السجل.
    """
    ct = ContentType.objects.get_for_model(obj, for_concrete_model=False)
    return ObjectACL.objects.filter(content_type=ct, object_id=obj.pk)
