# base/acl.py  (FULL REWRITE)
from __future__ import annotations

from typing import Optional, Iterable

from django.db import models
from django.db.models import Q
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType

from .company_context import get_allowed_company_ids
from .security_context import get_current_user_id


# ======================================================================================
#  Object-level ACL (Employee Management–ready)
#  - Core perms: view, change, delete, share, approve, assign, comment, export, rate, attach
#  - Extra perms: arbitrary names (strings) stored in JSONField → لا تحتاج ترقية سكيما لاحقًا
#  - Honors company scope + is_private when present on target model
# ======================================================================================

# مجموعة صلاحيات أساسية شائعة في أنظمة إدارة الموظفين
CORE_PERMS: tuple[str, ...] = (
    "view",     # قراءة السجل
    "change",   # تعديل السجل
    "delete",   # حذف السجل
    "share",    # مشاركة / منح وصول
    "approve",  # اعتماد (مثلاً إجازة/طلب/تقييم)
    "assign",   # إسناد (أصل/مهمة/مدرب…)
    "comment",  # تعليق/ملاحظات
    "export",   # تصدير بيانات هذا السجل
    "rate",     # تقييم (مهارة/أداء)
    "attach",   # رفع/إدارة مرفقات السجل
)


class ObjectACL(models.Model):
    """
    يمنح صلاحيات على سجل معيّن لمستخدم أو مجموعة.
    - يدعم مشاركة السجلات خارج نطاق الشركة عبر ACE.
    - يدعم is_private: السجلات الخاصة لا تُرى إلا بوجود ACE يمنح 'view'.
    - صلاحيات إضافية (extra_perms) بلا حدود بدون تعديل السكيما لاحقًا.
    """

    # ---------------------------- Target (generic) ----------------------------
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, db_index=True)
    object_id    = models.PositiveIntegerField(db_index=True)
    target       = GenericForeignKey("content_type", "object_id")

    # ----------------------------- Principal ---------------------------------
    user  = models.ForeignKey("base.User",  null=True, blank=True, on_delete=models.CASCADE, related_name="object_acls")
    group = models.ForeignKey("auth.Group", null=True, blank=True, on_delete=models.CASCADE, related_name="object_acls")

    # ------------------------------ Core perms -------------------------------
    can_view     = models.BooleanField(default=False)
    can_change   = models.BooleanField(default=False)
    can_delete   = models.BooleanField(default=False)
    can_share    = models.BooleanField(default=False)
    can_approve  = models.BooleanField(default=False)
    can_assign   = models.BooleanField(default=False)
    can_comment  = models.BooleanField(default=False)
    can_export   = models.BooleanField(default=False)
    can_rate     = models.BooleanField(default=False)
    can_attach   = models.BooleanField(default=False)

    # --------------------------- Extra (open-ended) --------------------------
    # قائمة صلاحيات نصّية إضافية (مثال: ["escalate", "archive", "sign"])
    extra_perms  = models.JSONField(default=list, blank=True)  # list[str]

    # ------------------------------- Admin -----------------------------------
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
            # لا بد من user أو group
            models.CheckConstraint(
                check=~(Q(user__isnull=True) & Q(group__isnull=True)),
                name="acl_has_principal",
            ),
            # لا بد من صلاحية واحدة على الأقل: (أحد الأعلام الأساسية) أو (extra_perms غير فارغة)
            models.CheckConstraint(
                check=(
                    Q(can_view=True) | Q(can_change=True) | Q(can_delete=True) |
                    Q(can_share=True) | Q(can_approve=True) | Q(can_assign=True) |
                    Q(can_comment=True) | Q(can_export=True) | Q(can_rate=True) | Q(can_attach=True) |
                    ~Q(extra_perms=[])
                ),
                name="acl_has_any_perm",
            ),
            # تفرد (object,user) عندما user ليس NULL
            models.UniqueConstraint(
                fields=["content_type", "object_id", "user"],
                name="acl_unique_ct_obj_user",
                condition=Q(user__isnull=False),
            ),
            # تفرد (object,group) عندما group وليس NULL
            models.UniqueConstraint(
                fields=["content_type", "object_id", "group"],
                name="acl_unique_ct_obj_group",
                condition=Q(group__isnull=False),
            ),
        ]

    # ------------------------------ Helpers ----------------------------------
    CORE_FLAG_BY_NAME: dict[str, str] = {
        "view": "can_view",
        "change": "can_change",
        "delete": "can_delete",
        "share": "can_share",
        "approve": "can_approve",
        "assign": "can_assign",
        "comment": "can_comment",
        "export": "can_export",
        "rate": "can_rate",
        "attach": "can_attach",
    }

    def __str__(self) -> str:
        who = self.user or self.group or "?"
        core = [name for name, flag in self.CORE_FLAG_BY_NAME.items() if getattr(self, flag)]
        extras = list(self.extra_perms or [])
        perms = ",".join(core + extras) if (core or extras) else "-"
        return f"ACL({self.content_type.model}:{self.object_id} → {who} [{perms}])"

    # Normalizes an action name to (core_flag or extra string)
    @classmethod
    def normalize_action(cls, action: str) -> tuple[Optional[str], Optional[str]]:
        a = (action or "").strip().lower()
        flag = cls.CORE_FLAG_BY_NAME.get(a)
        if flag:
            return flag, None
        return None, a  # treat as extra-perm (string)

    def grant(self, *, view=None, change=None, delete=None, share=None, approve=None,
              assign=None, comment=None, export=None, rate=None, attach=None,
              extras: Optional[Iterable[str]] = None) -> None:
        """
        set core flags when provided (not None) + merge extras.
        """
        for name, value in {
            "can_view": view, "can_change": change, "can_delete": delete,
            "can_share": share, "can_approve": approve, "can_assign": assign,
            "can_comment": comment, "can_export": export, "can_rate": rate, "can_attach": attach,
        }.items():
            if value is not None:
                setattr(self, name, bool(value))

        if extras:
            current = set(self.extra_perms or [])
            for x in extras:
                x = (x or "").strip().lower()
                if x:
                    current.add(x)
            self.extra_perms = sorted(current)

    def revoke_all(self) -> None:
        self.can_view = self.can_change = self.can_delete = False
        self.can_share = self.can_approve = self.can_assign = False
        self.can_comment = self.can_export = self.can_rate = self.can_attach = False
        self.extra_perms = []
        self.active = True  # لا نلغي السطر، فقط نصفر الصلاحيات

    def has(self, action: str) -> bool:
        flag, extra = self.normalize_action(action)
        if flag:
            return bool(getattr(self, flag))
        return (extra in (self.extra_perms or []))


class AccessControlledMixin(models.Model):
    """
    يضيف GenericRelation حتى يمكن للسجل استقبال ACEs (ObjectACL).
    """
    acls = GenericRelation(
        ObjectACL,
        content_type_field="content_type",
        object_id_field="object_id",
        related_query_name="target",
    )

    class Meta:
        abstract = True


# ======================================================================================
#  ACL-aware QuerySet/Manager
# ======================================================================================

def _user_from_ctx():
    # import متأخر لتجنب الدوران
    from .models import User
    uid = get_current_user_id()
    return User.objects.filter(id=uid).first() if uid else None


def _group_ids(user) -> list[int]:
    try:
        return list(user.groups.values_list("id", flat=True))
    except Exception:
        return []


class ACLQuerySet(models.QuerySet):
    """
    .with_acl(action[, user=...]) يفلتر النتائج وفق:
      1) صلاحية النموذج (Django model perm) للأفعال الأساسية view/change/delete فقط
      2) نطاق الشركات المسموح بها (company_id ∈ allowed) – إن وُجد حقل company
      3) إن كان الموديل ACL-aware (يورّث AccessControlledMixin):
         🔒 نُلزم وجود ACE دائمًا حتى داخل الشركة (لا تكفي العلنية is_private=False)
      4) إن لم يكن ACL-aware نطبّق منطق is_private: العامة تظهر داخل الشركة،
         والخاصّة لا تظهر إلا بوجود ACE
      5) مشاركة خارج الشركة عبر ACE
      6) للأفعال غير الأساسية (share/approve/assign/... أو أي extra): لا نفرض model perm؛
         يكفي رصد ACE المقابل.
    """
    def with_acl(self, action: str, user=None):
        user = user or getattr(self, "_acl_user", None) or _user_from_ctx()

        # غير الموثّق → لا بيانات
        if not user or not getattr(user, "is_authenticated", False):
            return self.none()

        # السوبر يوزر يرى كل شيء
        if getattr(user, "is_superuser", False):
            return self

        # 1) صلاحيات نموذج Django (نفرضها فقط للأفعال الأساسية الثلاثة)
        app = self.model._meta.app_label
        model = self.model._meta.model_name
        if action in ("view", "change", "delete"):
            codename = f"{app}.{action}_{model}"
            if not user.has_perm(codename):
                return self.none()

        # 2) نطاق الشركات / is_private / هل الموديل ACL-aware
        allowed = list(get_allowed_company_ids() or [])
        has_company = any(f.name == "company" for f in self.model._meta.get_fields())
        has_private = any(f.name == "is_private" for f in self.model._meta.get_fields())

        # موديلات تعتمد على ACL
        requires_ace = hasattr(self.model, "acls")

        # بناء ACE Subquery
        ct = ContentType.objects.get_for_model(self.model, for_concrete_model=False)
        g_ids = _group_ids(user)

        flag, extra = ObjectACL.normalize_action(action)
        acl_filter = Q(content_type=ct, active=True) & (Q(user=user) | Q(group_id__in=g_ids))
        if flag:
            acl_filter &= Q(**{flag: True})
        else:
            acl_filter &= Q(extra_perms__contains=[extra])

        acl_ids = ObjectACL.objects.filter(acl_filter).values("object_id")

        qs = self

        # -----------------------------
        # داخل الشركة
        # -----------------------------
        if has_company:
            base_in_company = qs.filter(company_id__in=allowed) if allowed else qs.none()
        else:
            base_in_company = qs

        # ---------------------------------------------------------
        # 🔥 تعديل حسب طلبك:
        # Department + Employee يجب أن يكونا ALWAYS_VISIBLE داخل الشركة
        # ---------------------------------------------------------

        if app == "hr" and model in ("department", "employee"):
            # تجاهل requires_ace بالكامل
            in_company = base_in_company

        else:
            # الوضع الطبيعي لبقية الموديلات
            if requires_ace:
                in_company = base_in_company.filter(pk__in=acl_ids)
            else:
                if has_private:
                    public_in_company = base_in_company.filter(Q(is_private=False) | Q(is_private__isnull=True))
                    private_in_company = base_in_company.filter(is_private=True, pk__in=acl_ids)
                    in_company = public_in_company.union(private_in_company)
                else:
                    in_company = base_in_company

        # -----------------------------
        # خارج الشركة (مشاركة صريحة)
        # -----------------------------
        if has_company:
            if allowed:
                shared = qs.filter(~Q(company_id__in=allowed), pk__in=acl_ids)
            else:
                shared = qs.filter(pk__in=acl_ids)
            return in_company.union(shared)

        return in_company



class ACLManager(models.Manager.from_queryset(ACLQuerySet)):
    use_in_migrations = True

    def for_user(self, user):
        qs = self.get_queryset().all()
        qs._acl_user = user
        return qs
