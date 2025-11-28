# base/acl_service.py  (FULL REWRITE to match the new base/acl.py)
from __future__ import annotations
from typing import Iterable, Optional, Sequence, Tuple

from django.contrib.contenttypes.models import ContentType
from django.db.models import Q

from hr.models import Department , Employee
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
# full updated apply_default_acl implementation
from django.contrib.auth.models import Group, Permission
from hr.models import Department, Employee

def _get_base_department_for_obj(obj):
    """
    Return the department related to obj:
      - if obj is Department -> itself
      - if obj has department_id -> obj.department
      - if obj has employee_id -> obj.employee.department
    """
    if isinstance(obj, Department):
        return obj

    if hasattr(obj, "department_id") and getattr(obj, "department_id"):
        return getattr(obj, "department", None)

    if hasattr(obj, "employee_id") and getattr(obj, "employee_id"):
        emp = getattr(obj, "employee", None)
        if isinstance(emp, Employee) and getattr(emp, "department_id", None):
            return getattr(emp, "department", None)

    return None

def apply_default_acl(obj):
    """
    =====================================================================
    Default ACL Rules (Odoo-style) applied on ANY object saved in system.
    =====================================================================

    GLOBAL POLICY:
    1) Owner (created_by) → full access
    2) HR Managers        → full access   (permission: hr.manage_all_hr)
    3) Employee          → view + change (his own Employee record)
    4) Department Manager Hierarchy:
         - Manager of department of object  → view/change/approve/assign
         - Manager of parent departments    → view/change/approve/assign
         - Manager of the department itself → also gets inheritance rules
    5) For Department objects:
         - Managers of sibling departments get view-only (coordination)
         - Manager of this department gets view-only on parents

    ASSETS SPECIFIC:
    6) Asset.holder.user:
         → view + change on Asset
    7) AssetAssignment.employee.user:
         → view on Assignment
         → view + change on related Asset

    NOTE:
    - ACL must never crash object save, therefore exceptions are swallowed
      where needed.
    - All permissions are additive (never revoked here).
    =====================================================================
    """

    # Lazy imports inside function (to avoid circular dependencies)
    from django.contrib.auth.models import Group, Permission
    try:
        from assets.models import Asset, AssetAssignment
    except Exception:
        Asset = None
        AssetAssignment = None

    try:
        from performance.models import Evaluation
    except Exception:
        Evaluation = None

    # Nothing to apply on objects without PK
    if not getattr(obj, "pk", None):
        return

    # ============================================================
    # (1) Owner (created_by) → full access
    # ============================================================
    owner = getattr(obj, "created_by", None)
    if owner:
        grant_access(
            obj,
            user=owner,
            view=True, change=True, delete=True,
            approve=True, assign=True, share=True,
        )

    # ============================================================
    # (2) HR Managers Groups → full access
    # ============================================================
    try:
        perm = Permission.objects.get(
            content_type__app_label="hr",
            codename="manage_all_hr"
        )
        hr_groups = Group.objects.filter(permissions=perm)
        for g in hr_groups:
            grant_access(
                obj,
                group=g,
                view=True, change=True, delete=True,
                approve=True, assign=True, share=True,
            )
    except Permission.DoesNotExist:
        pass

    # ============================================================
    # (3) Employee itself → view + change
    # ============================================================
    if isinstance(obj, Employee) and getattr(obj, "user_id", None):
        grant_access(
            obj,
            user=obj.user,
            view=True,
            change=True,
        )

    # ============================================================
    # (4) Asset holder → view + change on Asset
    # ============================================================
    if Asset and isinstance(obj, Asset):
        holder = getattr(obj, "holder", None)
        holder_user = getattr(holder, "user", None) if holder else None
        if holder_user:
            grant_access(
                obj,
                user=holder_user,
                view=True,
                change=True,
            )

    # ============================================================
    # (5) AssetAssignment.employee:
    #       → view on Assignment
    #       → view + change on related Asset
    # ============================================================
    if AssetAssignment and isinstance(obj, AssetAssignment):
        emp = getattr(obj, "employee", None)
        emp_user = getattr(emp, "user", None) if emp else None
        if emp_user:
            grant_access(
                obj,
                user=emp_user,
                view=True,
            )
            asset = getattr(obj, "asset", None)
            if asset:
                grant_access(
                    asset,
                    user=emp_user,
                    view=True,
                    change=True,
                )

    # ============================================================
    # (5.1) Evaluation.employee.user → view on Evaluation
    # ============================================================
    if Evaluation and isinstance(obj, Evaluation):
        emp = getattr(obj, "employee", None)
        emp_user = getattr(emp, "user", None) if emp else None
        if emp_user:
            grant_access(
                obj,
                user=emp_user,
                view=True,
            )

    # ============================================================
    # (6) Department hierarchy managers → operational rights
    # ============================================================
    base_dept = _get_base_department_for_obj(obj)
    if not isinstance(base_dept, Department):
        return  # Objects without department hierarchy stop here

    seen = set()
    cur = base_dept
    while cur:
        mgr = getattr(cur, "manager", None)
        mgr_user = getattr(mgr, "user", None) if mgr else None
        if mgr_user and mgr_user.pk not in seen:
            grant_access(
                obj,
                user=mgr_user,
                view=True,
                change=True,
                approve=True,
                assign=True,
            )
            seen.add(mgr_user.pk)
        cur = cur.parent

    # ============================================================
    # (7) Manager of this department → view-only on parents
    # ============================================================
    try:
        base_mgr = getattr(base_dept, "manager", None)
        base_mgr_user = getattr(base_mgr, "user", None) if base_mgr else None
        if base_mgr_user:
            parent = base_dept.parent
            seen_view = set()
            while parent:
                if base_mgr_user.pk not in seen_view:
                    grant_access(
                        parent,
                        user=base_mgr_user,
                        view=True,
                        change=False,
                        approve=False,
                        assign=False,
                        share=False,
                    )
                    seen_view.add(base_mgr_user.pk)
                parent = parent.parent
    except Exception:
        pass

    # ============================================================
    # (8) Department objects → sibling managers get view-only
    # ============================================================
    if isinstance(obj, Department):
        parent = getattr(obj, "parent", None)
        if parent:
            try:
                siblings = parent.children.exclude(pk=obj.pk)
                for s in siblings:
                    m = getattr(s, "manager", None)
                    mu = getattr(m, "user", None) if m else None
                    if mu:
                        grant_access(
                            obj,
                            user=mu,
                            view=True,
                            change=False,
                        )
            except Exception:
                pass


# === TEAM VISIBILITY (manager + peers) =======================================
from collections import defaultdict
from django.db.models.signals import post_save
from django.dispatch import receiver

from hr.models import Department, Employee  # غالباً موجودة بالأعلى، إن كانت موجودة لا تكررها

TEAM_EXTRA_FLAG = "team_visibility"


def rebuild_team_visibility():
    """
    يجعل كل موظف يرى:
      - مديره المباشر (Employee.manager)
      - زملاءه الذين لهم نفس المدير

    المنطق:
      - نبني ACEs جديدة بعَلم extra_perms=['team_visibility']
      - قبل البناء نحذف كل ACEs القديمة التي تحمل هذا العلم حتى لا تتراكم.
    """
    from django.contrib.contenttypes.models import ContentType
    from .acl import ObjectACL   # نفس الموديل الموجود في هذا الملف
    from .acl_service import grant_access  # إذا أعطاك import دائري، تجاهله هنا لأننا في نفس الملف

    # تجنّب الاستيراد الدائري: بما أننا داخل نفس الملف يمكننا استخدام grant_access مباشرة بدون import
    ct = ContentType.objects.get_for_model(Employee, for_concrete_model=False)

    # 1) حذف كل ACEs السابقة الخاصة بـ team_visibility
    ObjectACL.objects.filter(
        content_type=ct,
        extra_perms__contains=[TEAM_EXTRA_FLAG],
    ).delete()

    # 2) جمع الموظفين الذين لديهم user ومدير
    employees = (
        Employee.objects.filter(
            active=True,
            user__isnull=False,
            manager__isnull=False,
        )
        .select_related("user", "manager")
        .only("id", "user_id", "manager_id", "company_id", "active")
    )

    # تقسيمهم حسب المدير
    teams: dict[int, list[Employee]] = defaultdict(list)
    for emp in employees:
        teams[emp.manager_id].append(emp)

    # 3) بناء ACEs
    for manager_id, team in teams.items():
        try:
            manager_emp = Employee.objects.get(pk=manager_id, active=True)
        except Employee.DoesNotExist:
            manager_emp = None

        # (أ) كل فرد في الفريق يرى المدير
        if manager_emp and manager_emp.user_id:
            for emp in team:
                if not emp.user_id:
                    continue
                grant_access(
                    manager_emp,
                    user=emp.user,
                    view=True,
                    extras=[TEAM_EXTRA_FLAG],
                )

        # (ب) كل فرد يرى زملاءه (نفس المدير)
        for emp in team:
            if not emp.user_id:
                continue
            for peer in team:
                if peer.pk == emp.pk or not peer.user_id:
                    continue
                grant_access(
                    peer,
                    user=emp.user,
                    view=True,
                    extras=[TEAM_EXTRA_FLAG],
                )


@receiver(post_save, sender=Employee)
def _sync_team_visibility_on_employee_save(sender, instance, **kwargs):
    """
    أي تعديل على موظف (خصوصاً تغيير manager) يعيد بناء رؤية الفرق.
    هذا أبسط حل الآن (يعيد بناء كل الفرق) ومناسب لعدد موظفينك الحالي.
    """
    rebuild_team_visibility()


