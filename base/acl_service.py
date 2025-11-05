# base/acl_service.py  (FULL REWRITE to match the new base/acl.py)
from __future__ import annotations
from typing import Iterable, Optional, Sequence, Tuple

from django.contrib.contenttypes.models import ContentType
from django.db.models import Q

from .acl import ObjectACL, CORE_PERMS

# --------------------------------------------------------------------------------------
# ملاحظات سريعة:
# - يدعم منح/تعديل/سحب صلاحيات أساسية (view/change/delete/share/approve/assign/comment/export/rate/attach)
#   + صلاحيات إضافية مفتوحة عبر extra_perms (قائمة أسماء نصية) بدون ترقية سكيما لاحقًا.
# - grant_access: يحدّث أو ينشئ ACE ويُعدّل فقط الأعلام التي تم تمريرها (غير None) ويدمج extras.
# - revoke_access: يحذف ACE بالكامل (ل principal معيّن) أو يسحب صلاحيات معيّنة فقط دون حذف السطر.
# - has_perm: يفحص صلاحية على سجل لمستخدم (يشمل مجموعاته)، يعتمد الـACL فقط (بدون منطق الشركة).
#   للفلترة بالسياق الكامل (شركة/خصوصية/مشاركة) استعمل QuerySet.with_acl(...) كما في acl.py.
# - list_access: يرجع جميع ACEs الخاصة بالسجل.
# --------------------------------------------------------------------------------------


# خريطة الاسم → اسم الحقل البولياني في نموذج الـACL
_CORE_FLAG_BY_NAME = ObjectACL.CORE_FLAG_BY_NAME  # نفس المعجم المعرّف داخل ObjectACL


def _ct_and_pk(obj) -> Tuple[ContentType, int]:
    return ContentType.objects.get_for_model(obj, for_concrete_model=False), obj.pk


def _principal_filter(user=None, group=None) -> Q:
    q = Q()
    if user is not None:
        q &= Q(user=user)
    if group is not None:
        q &= Q(group=group)
    return q


def _normalize_extras(extras: Optional[Iterable[str]]) -> list[str]:
    if not extras:
        return []
    out: set[str] = set()
    for x in extras:
        x = (x or "").strip().lower()
        if x:
            out.add(x)
    return sorted(out)


# ======================================================================================
# واجهات المنح/السحب
# ======================================================================================

def grant_access(
    obj,
    *,
    user=None,
    group=None,
    # الأعلام الأساسية (مرّر None لترك القيمة كما هي، و True/False لضبطها)
    view: Optional[bool] = None,
    change: Optional[bool] = None,
    delete: Optional[bool] = None,
    share: Optional[bool] = None,
    approve: Optional[bool] = None,
    assign: Optional[bool] = None,
    comment: Optional[bool] = None,
    export: Optional[bool] = None,
    rate: Optional[bool] = None,
    attach: Optional[bool] = None,
    # صلاحيات إضافية مفتوحة
    extras: Optional[Iterable[str]] = None,
    # إعدادات إدارية
    active: Optional[bool] = None,
    company=None,
):
    """
    امنح/حدّث ACE على سجل محدّد (update_or_create):
      - يضبط فقط الأعلام التي تم تمريرها (غير None).
      - يدمج extra_perms دون تكرار.
      - لا يلمس الأعلام غير الممرّرة.
    """
    ct, pk = _ct_and_pk(obj)

    # جهّز أعلام الصلاحيات الممرّرة كافتراضات للإنشاء الأولي (حتى لا نخالف قيد DB)
    core_defaults = {
        "can_view": bool(view) if view is not None else False,
        "can_change": bool(change) if change is not None else False,
        "can_delete": bool(delete) if delete is not None else False,
        "can_share": bool(share) if share is not None else False,
        "can_approve": bool(approve) if approve is not None else False,
        "can_assign": bool(assign) if assign is not None else False,
        "can_comment": bool(comment) if comment is not None else False,
        "can_export": bool(export) if export is not None else False,
        "can_rate": bool(rate) if rate is not None else False,
        "can_attach": bool(attach) if attach is not None else False,
    }
    extras_list = _normalize_extras(extras)

    defaults = {
        "active": True if active is None else bool(active),
        "company": company,
        **core_defaults,
    }
    if extras_list:
        defaults["extra_perms"] = extras_list

    ace, created = ObjectACL.objects.get_or_create(
        content_type=ct,
        object_id=pk,
        user=user,
        group=group,
        defaults=defaults,
    )

    # اضبط الأعلام الأساسية التي تم تمريرها فقط
    core_updates = {
        "can_view": view, "can_change": change, "can_delete": delete,
        "can_share": share, "can_approve": approve, "can_assign": assign,
        "can_comment": comment, "can_export": export, "can_rate": rate, "can_attach": attach,
    }
    for field_name, maybe_value in core_updates.items():
        if maybe_value is not None:
            setattr(ace, field_name, bool(maybe_value))

    # دمج extra_perms
    new_extras = _normalize_extras(extras)
    if new_extras:
        current = set(ace.extra_perms or [])
        current.update(new_extras)
        ace.extra_perms = sorted(current)

    # active / company
    if active is not None:
        ace.active = bool(active)
    if company is not None:
        ace.company = company

    ace.save()
    return ace


def revoke_access(
    obj,
    *,
    user=None,
    group=None,
    only: Optional[Sequence[str]] = None,
    keep_row_if_empty: bool = False,
):
    """
    اسحب الوصول:
      - إن لم تُمرَّر 'only' → يُحذف ACE بالكامل (لـ user/group).
      - إن مُرِّرت 'only' → تُسحب صلاحيات محدّدة فقط (core/extra)،
        وإذا أصبح السطر بلا أي صلاحية:
          - يحذف السطر كليًا، إلا إذا keep_row_if_empty=True فيُترك بلا صلاحيات.
    """
    ct, pk = _ct_and_pk(obj)
    qs = ObjectACL.objects.filter(content_type=ct, object_id=pk).filter(_principal_filter(user, group))
    if not only:
        # حذف ACE بالكامل
        return qs.delete()

    # سحب صلاحيات محددة فقط
    names = [(n or "").strip().lower() for n in only if (n or "").strip()]
    for ace in qs:
        # اسحب الأعلام الأساسية
        for name in names:
            flag = _CORE_FLAG_BY_NAME.get(name)
            if flag:
                setattr(ace, flag, False)

        # اسحب من extras
        if ace.extra_perms:
            ace.extra_perms = sorted(x for x in ace.extra_perms if x not in names)

        # هل بقي أي صلاحية؟
        still_has = (
            ace.can_view or ace.can_change or ace.can_delete or ace.can_share or
            ace.can_approve or ace.can_assign or ace.can_comment or ace.can_export or
            ace.can_rate or ace.can_attach or bool(ace.extra_perms)
        )
        if still_has or keep_row_if_empty:
            ace.save()
        else:
            ace.delete()
    return None


# ======================================================================================
# الفحص والقوائم
# ======================================================================================

def has_perm(obj, user, action: str) -> bool:
    """
    فحص صلاحية كائنية عبر الـACL فقط (لا يشمل سكوب الشركة/الخصوصية).
    للفلترة بحسب الشركة/الخصوصية استخدم QuerySet.with_acl(..) كما في base/acl.py.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True

    action = (action or "").strip().lower()
    ct, pk = _ct_and_pk(obj)

    # مجموعات المستخدم
    group_ids = list(user.groups.values_list("id", flat=True))

    # بنية استعلام ACE
    q = Q(content_type=ct, object_id=pk, active=True) & (Q(user=user) | Q(group_id__in=group_ids))

    flag, extra = ObjectACL.normalize_action(action)  # يعالج الأسماء الأساسية + extras
    if flag:
        q &= Q(**{flag: True})
    else:
        q &= Q(extra_perms__contains=[extra])

    return ObjectACL.objects.filter(q).exists()


def list_access(obj):
    """
    جميع ACEs الخاصة بالسجل.
    """
    ct, pk = _ct_and_pk(obj)
    return ObjectACL.objects.filter(content_type=ct, object_id=pk)


# ======================================================================================
# مُساعِدات عملية (اختيارية) للسيناريوهات المتكررة
# ======================================================================================

def set_access(
    obj,
    *,
    user=None,
    group=None,
    # مجموعة أسماء صلاحيات (أساسية/موسّعة). مثال: ["view", "change", "approve", "escalate"]
    perms: Optional[Iterable[str]] = None,
    active: Optional[bool] = None,
    company=None,
):
    """
    يضبط مجموعة صلاحيات معيّنة دفعة واحدة (يُفعّل المذكور ويُبطّل غير المذكور كلها)،
    مع الحفاظ على السطر نفسه.
    """
    ct, pk = _ct_and_pk(obj)
    ace, _ = ObjectACL.objects.get_or_create(
        content_type=ct,
        object_id=pk,
        user=user,
        group=group,
        defaults={"active": True if active is None else bool(active), "company": company},
    )

    # أعلام أساسية → False ثم True لما هو مطلوب
    for flag in _CORE_FLAG_BY_NAME.values():
        setattr(ace, flag, False)

    extras_set = set()

    if perms:
        for name in perms:
            name = (name or "").strip().lower()
            if not name:
                continue
            flag = _CORE_FLAG_BY_NAME.get(name)
            if flag:
                setattr(ace, flag, True)
            else:
                extras_set.add(name)

    ace.extra_perms = sorted(extras_set)

    if active is not None:
        ace.active = bool(active)
    if company is not None:
        ace.company = company

    ace.save()
    return ace


def grant_bulk(objs: Iterable, *, user=None, group=None, perms: Iterable[str] | None = None):
    """
    منح مجموعة صلاحيات لأكثر من سجل دفعة واحدة.
    """
    perms = list(perms or [])
    core_kwargs = {}
    extras: list[str] = []
    for p in perms:
        p = (p or "").strip().lower()
        if not p:
            continue
        flag = _CORE_FLAG_BY_NAME.get(p)
        if flag:
            core_kwargs[flag.replace("can_", "")] = True  # "can_view" → view=True
        else:
            extras.append(p)

    for obj in objs:
        grant_access(obj, user=user, group=group, extras=extras, **core_kwargs)



# === DEFAULT GLOBAL POLICY (company-wide) ====================================
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

def apply_default_acl(obj):
    """
    يطبّق السياسة الافتراضية للعناصر (Global) بدون الاعتماد على اسم أي مجموعة:
      - المالك (created_by): view/change/delete/approve/assign/share
      - HR Manager (أي مجموعة تحمل permission: hr.manage_all_hr):
            view/change/delete/approve/assign/share
      - مدير القسم (إن وُجد على السجل الحالي):
            view/change/approve/assign
    ملاحظة: هذه الدالة idempotent (تعيد ضبط/إنشاء ACE حسب الحاجة).
    """
    # 0) سلامة: لا نعمل على كائن بلا PK
    if not getattr(obj, "pk", None):
        return

    # 1) مالك السجل (created_by)
    owner = getattr(obj, "created_by", None)
    if owner:
        grant_access(
            obj,
            user=owner,
            view=True, change=True, delete=True, approve=True, assign=True, share=True,
        )

    # 2) HR Manager: أي مجموعة لديها permission codename = manage_all_hr (app_label=hr)
    try:
        perm = Permission.objects.get(
            content_type__app_label="hr",
            codename="manage_all_hr",
        )
        hr_groups = Group.objects.filter(permissions=perm)
        for g in hr_groups:
            grant_access(
                obj,
                group=g,
                view=True, change=True, delete=True, approve=True, assign=True, share=True,
            )
    except Permission.DoesNotExist:
        # لو الصلاحية غير موجودة بعد، نتجاوز بهدوء (لا نكسر الحفظ)
        pass

    # 3) مدير القسم (HR): إن كان للكائن 'department' وله 'manager' مرتبط بمستخدم
    #    - هذا يخص نماذج HR (مثل Employee) التي تحتوي field department → manager
    dept = getattr(obj, "department", None)
    if dept and getattr(dept, "manager_id", None) and getattr(dept.manager, "user_id", None):
        grant_access(
            obj,
            user=dept.manager.user,  # مستخدم مدير القسم
            view=True, change=True, approve=True, assign=True,
        )
