# base/acl.py
from __future__ import annotations
from django.db import models
from django.db.models import Q
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType

from .company_context import get_allowed_company_ids
from .security_context import get_current_user_id

# ------------------ Object-level ACL ------------------
# هذا الكود يتعامل تلقائيًا مع حقول company و is_private إن وُجدت في الموديل.

class ObjectACL(models.Model):
    """
    يمنح صلاحيات على سجل معيّن لمستخدم/مجموعة.
    - يمكنه تخطي قيد الشركة (sharing عبر ACE).
    - create ليس منطقيًا على سجل قائم، لذا ندير view/change/delete فقط.
    """
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, db_index=True)
    object_id    = models.PositiveIntegerField(db_index=True)
    target       = GenericForeignKey("content_type", "object_id")

    user  = models.ForeignKey("base.User", null=True, blank=True, on_delete=models.CASCADE, related_name="object_acls")
    group = models.ForeignKey("auth.Group", null=True, blank=True, on_delete=models.CASCADE, related_name="object_acls")

    can_view   = models.BooleanField(default=False)
    can_change = models.BooleanField(default=False)
    can_delete = models.BooleanField(default=False)

    active  = models.BooleanField(default=True, db_index=True)
    company = models.ForeignKey("base.Company", null=True, blank=True, on_delete=models.PROTECT)

    class Meta:
        db_table = "object_acl"
        indexes = [
            models.Index(fields=["content_type", "object_id", "active"], name="acl_ct_obj_active_idx"),
            models.Index(fields=["user"],  name="acl_user_idx"),
            models.Index(fields=["group"], name="acl_group_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                check=~(Q(user__isnull=True) & Q(group__isnull=True)),
                name="acl_has_principal",
            ),
            models.CheckConstraint(
                check=Q(can_view=True) | Q(can_change=True) | Q(can_delete=True),
                name="acl_has_perm",
            ),
        ]

    def __str__(self) -> str:
        who = self.user or self.group or "?"
        perms = ",".join(p for p, v in [("view", self.can_view), ("change", self.can_change), ("delete", self.can_delete)] if v)
        return f"ACL({self.content_type.model}:{self.object_id} → {who} [{perms}])"


class AccessControlledMixin(models.Model):
    """
    تضيف GenericRelation حتى يمكن للسجل استقبال ACEs.
    """
    acls = GenericRelation(
        ObjectACL,
        content_type_field="content_type",
        object_id_field="object_id",
        related_query_name="target",
    )

    class Meta:
        abstract = True


# ------------------ ACL-aware QuerySet/Manager ------------------

def _user_from_ctx():
    from .models import User  # import متأخر لتجنب الدوران
    uid = get_current_user_id()
    return User.objects.filter(id=uid).first() if uid else None

def _group_ids(user) -> list[int]:
    try:
        return list(user.groups.values_list("id", flat=True))
    except Exception:
        return []

class ACLQuerySet(models.QuerySet):
    """
    استخدم .with_acl(action) لفلترة النتائج وفق:
      - صلاحيات الموديل (Django Permissions)
      - نطاق الشركات المسموح بها
      - القيد الجديد: is_private داخل الشركة (لا تُعرض إلا بوجود ACE)
      - مشاركة السجلات خارج الشركة عبر ACE
    """
    def with_acl(self, action: str, user=None):
        user = user or getattr(self, "_acl_user", None) or _user_from_ctx()
        if not user or not user.is_authenticated or user.is_superuser:
            return self

        app = self.model._meta.app_label
        model = self.model._meta.model_name
        codename = {
            "view":   f"{app}.view_{model}",
            "change": f"{app}.change_{model}",
            "delete": f"{app}.delete_{model}",
        }[action]
        if not user.has_perm(codename):
            return self.none()

        allowed = list(get_allowed_company_ids() or [])
        has_company_field = any(f.name == "company" for f in self.model._meta.get_fields())
        has_private_field = any(f.name == "is_private" for f in self.model._meta.get_fields())

        # ACL subquery
        ct = ContentType.objects.get_for_model(self.model, for_concrete_model=False)
        g_ids = _group_ids(user)
        flag = {"view":"can_view", "change":"can_change", "delete":"can_delete"}[action]
        acl_ids = ObjectACL.objects.filter(
            content_type=ct, active=True
        ).filter(
            Q(user=user) | Q(group_id__in=g_ids)
        ).filter(**{flag: True}).values("object_id")

        qs = self

        # 1) داخل الشركة
        if has_company_field and allowed:
            in_company = qs.filter(company_id__in=allowed)
            if has_private_field:
                # العامة داخل الشركة (is_private=False) + الخاصة الممنوحة بالـ ACE
                public_in_company  = in_company.filter(Q(is_private=False) | Q(is_private__isnull=True))
                private_in_company = in_company.filter(is_private=True, pk__in=acl_ids)
                in_company = public_in_company.union(private_in_company)
        else:
            # موديلات بلا شركة: لو عندك is_private، أخفِ الخاصة إلا بوجود ACE
            if has_private_field:
                public_no_company  = qs.filter(Q(is_private=False) | Q(is_private__isnull=True))
                private_no_company = qs.filter(is_private=True, pk__in=acl_ids)
                in_company = public_no_company.union(private_no_company)
            else:
                in_company = qs

        # 2) خارج الشركة — متاحة فقط إن وُجد ACE (sharing)
        if has_company_field and allowed:
            shared = qs.filter(~Q(company_id__in=allowed), pk__in=acl_ids)
            return in_company.union(shared)

        return in_company

class ACLManager(models.Manager.from_queryset(ACLQuerySet)):
    use_in_migrations = True
    def for_user(self, user):
        qs = self.get_queryset().all()
        qs._acl_user = user
        return qs
