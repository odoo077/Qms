from __future__ import annotations
from typing import Iterable, Sequence
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.core.exceptions import PermissionDenied
from base.acl_service import has_perm as acl_has_perm

from .models import ChatterMessage, ChatterFollower, ChatterAttachment

# النتيجة: الرسائل تُقرأ/تُنشر فقط إذا كان لدى المستخدم حق الوصول الكائني على الهدف (view/change)، بدون أي تساهل.
def _can_read(obj, user) -> bool:
    # اقرأ فقط إن كان يملك view على السجل الهدف
    return bool(user and acl_has_perm(obj, user, "view"))

def _can_post(obj, user) -> bool:
    # الكتابة مشروطة بـ change على الهدف أو صلاحية نشر عامة على الشاتِر
    return bool(user and (acl_has_perm(obj, user, "change") or user.has_perm("chatter.post_chatter_message")))


def _ct_and_id(target):
    return ContentType.objects.get_for_model(target.__class__), target.pk


@transaction.atomic
def follow(target, *, user=None, employee=None):
    ct, oid = _ct_and_id(target)
    follower = ChatterFollower.objects.get_or_create(
        content_type=ct, object_id=oid, user=user, employee=employee, defaults={}
    )[0]
    return follower


@transaction.atomic
def unfollow(target, *, user=None, employee=None):
    ct, oid = _ct_and_id(target)
    qs = ChatterFollower.objects.filter(content_type=ct, object_id=oid)
    if user:
        qs = qs.filter(user=user)
    if employee:
        qs = qs.filter(employee=employee)
    qs.delete()


@transaction.atomic
def post_message(target, *, author_user, body: str, author_employee=None,
                 files: Sequence = (), notify_followers: bool = True) -> ChatterMessage:
    if not _can_read(target, author_user) or not _can_post(target, author_user):
        raise PermissionDenied("You are not allowed to post on this record.")

    ct, oid = _ct_and_id(target)
    msg = ChatterMessage.objects.create(
        content_type=ct,
        object_id=oid,
        author_user=author_user,
        author_employee=author_employee,
        body=body,
        company_id=getattr(target, "company_id", None),
    )

    # مرفقات اختيارية
    for f in files or ():
        ChatterAttachment.objects.create(message=msg, file=f)

    # متابعة تلقائية للكاتب
    try:
        follow(target, user=author_user, employee=author_employee)
    except Exception:
        pass

    # (اختياري) إشعار المتابعين — يمكنك لاحقًا ربطه بمنظومة إشعارك
    if notify_followers:
        # نقطة تمديد مستقبلية: إرسال إشعار داخلي/بريد/إشعار فوري…
        pass

    return msg


def list_messages(target, limit: int = 50) -> Iterable[ChatterMessage]:
    ct, oid = _ct_and_id(target)
    return ChatterMessage.objects.filter(content_type=ct, object_id=oid).select_related(
        "author_user", "author_employee", "company"
    ).order_by("-created_at")[:limit]


def list_followers(target) -> Iterable[ChatterFollower]:
    ct, oid = _ct_and_id(target)
    return ChatterFollower.objects.filter(content_type=ct, object_id=oid).select_related(
        "user", "employee", "company"
    )
