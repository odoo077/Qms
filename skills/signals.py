# skills/signals.py
# ============================================================
# Signals for Skills app (Guardian-ready)
# - منح صلاحيات على مستوى الكائن عبر django-guardian
# - المحافظة على صلاحيات الموظف/المالك عند الإنشاء أو تغيير الارتباط
# ============================================================

from __future__ import annotations

from typing import Optional

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from base.acl_service import grant_access, revoke_access

from . import models


# ============================================================
# Helpers (Arabic comments)
# ============================================================

def _grant_if_user(user, codename: str, obj) -> None:
    """
    يمنح صلاحية واحدة على الكائن عبر نظام الـACL.
    يدعم codenames على نسق Guardian مثل "skills.view_employeeskill"
    أو أسماء مباشرة مثل "view" أو "approve"… إلخ.
    - الأساسية: view/change/delete/share/approve/assign/comment/export/rate/attach
    - غير الأساسية تُسجَّل كـ extra_perms.
    """
    if user is None:
        return

    # استخرج الإجراء من codename (مثال: "skills.view_employeeskill" → "view")
    name = (codename or "").strip().lower()
    name = name.split(".")[-1]          # "view_employeeskill"
    action = name.split("_", 1)[0]      # "view"

    core = {"view", "change", "delete", "share", "approve", "assign", "comment", "export", "rate", "attach"}

    if action in core:
        grant_access(obj, user=user, **{action: True})
    else:
        # تُخزَّن كصلاحية إضافية مفتوحة
        grant_access(obj, user=user, extras=[action])


def _grant_many(user, perms: list[str], obj) -> None:
    """
    يمنح مجموعة صلاحيات كائنية دفعة واحدة عبر نظام الـACL.
    - الأسماء الأساسية: view/change/delete/share/approve/assign/comment/export/rate/attach
    - أي أسماء أخرى ستُخزَّن في extra_perms تلقائيًا.
    """
    if user is None:
        return
    core = {"view": False, "change": False, "delete": False, "share": False,
            "approve": False, "assign": False, "comment": False, "export": False,
            "rate": False, "attach": False}
    extras = []
    for p in (perms or []):
        p = (p or "").strip().lower()
        if p in core:
            core[p] = True
        else:
            extras.append(p)
    grant_access(
        obj,
        user=user,
        view=core["view"], change=core["change"], delete=core["delete"],
        share=core["share"], approve=core["approve"], assign=core["assign"],
        comment=core["comment"], export=core["export"], rate=core["rate"], attach=core["attach"],
        extras=extras or None,
    )


def _remove_many(user, perms: list[str], obj) -> None:
    """
    يسحب صلاحيات محددة (core أو extra) للمستخدم على الكائن.
    """
    if user is None:
        return
    names = [(p or "").strip().lower() for p in (perms or []) if (p or "").strip()]
    if not names:
        return
    revoke_access(obj, user=user, only=names)


def _employee_user_of(instance) -> Optional[models.User]:
    """
    جلب مستخدم الموظف المرتبط بالسجل (إن وُجد).
    - للـ EmployeeSkill و ResumeLine: instance.employee.user
    """
    try:
        emp = getattr(instance, "employee", None)
        return getattr(emp, "user", None)
    except Exception:
        return None


# ============================================================
# EmployeeSkill — منح/تحديث صلاحيات الكائن
# ============================================================

# قبل الحفظ: نلتقط قيمة الموظف القديمة كي نعرف لاحقًا إن تغيّر الموظف
@receiver(pre_save, sender=models.EmployeeSkill)
def _employeeskill_capture_old_employee(sender, instance: models.EmployeeSkill, **kwargs):
    if not instance.pk:
        instance._old_employee_id = None
        return
    try:
        old = sender.objects.only("employee_id").get(pk=instance.pk)
        instance._old_employee_id = old.employee_id
    except sender.DoesNotExist:
        instance._old_employee_id = None


@receiver(post_save, sender=models.EmployeeSkill)
def _employeeskill_assign_object_perms(sender, instance: models.EmployeeSkill, created: bool, **kwargs):
    """
    منطق الصلاحيات (Object-Level) للـ EmployeeSkill:
      1) عند الإنشاء:
         - created_by: view + change (+ rate_skill إن رغبت)
         - employee.user: view فقط (ليتمكن الموظف من رؤية مهاراته)
      2) عند التعديل:
         - إن تغيّر الموظف: انقل view من مستخدم الموظف القديم إلى مستخدم الموظف الجديد
    """
    # أسماء صلاحيات Guardian (codenames) كما ولّدها Django:
    VIEW = "skills.view_employeeskill"
    CHANGE = "skills.change_employeeskill"
    RATE = "skills.rate_skill"  # معرفة داخل Meta.permissions في الموديل

    owner = getattr(instance, "created_by", None)
    emp_user_new = _employee_user_of(instance)

    if created:
        # مالك السجل: عرض + تعديل + تقييم (rate)
        _grant_many(owner, ["view", "change", "rate"], instance)
        # مستخدم الموظف: عرض فقط
        _grant_many(emp_user_new, ["view"], instance)
        return

    # تحديث: إن تغيّر الموظف ننقل صلاحية العرض من القديم للجديد
    old_emp_id = getattr(instance, "_old_employee_id", None)
    if old_emp_id is not None and old_emp_id != getattr(instance, "employee_id", None):
        try:
            old_emp = models.Employee.objects.only("user_id").get(pk=old_emp_id)
            emp_user_old = getattr(old_emp, "user", None)
        except models.Employee.DoesNotExist:
            emp_user_old = None

        _remove_many(emp_user_old, ["view"], instance)
        _grant_many(emp_user_new, ["view"], instance)



# ============================================================
# ResumeLine — منح/تحديث صلاحيات الكائن
# ============================================================

@receiver(pre_save, sender=models.ResumeLine)
def _resumeline_capture_old_employee(sender, instance: models.ResumeLine, **kwargs):
    if not instance.pk:
        instance._old_employee_id = None
        return
    try:
        old = sender.objects.only("employee_id").get(pk=instance.pk)
        instance._old_employee_id = old.employee_id
    except sender.DoesNotExist:
        instance._old_employee_id = None


@receiver(post_save, sender=models.ResumeLine)
def _resumeline_assign_object_perms(sender, instance: models.ResumeLine, created: bool, **kwargs):
    """
    منطق الصلاحيات (Object-Level) للـ ResumeLine:
      1) عند الإنشاء:
         - created_by: view + change
         - employee.user: view فقط
      2) عند التعديل:
         - إن تغيّر الموظف: انقل view من مستخدم الموظف القديم إلى مستخدم الموظف الجديد
    """
    VIEW = "skills.view_resumeline"
    CHANGE = "skills.change_resumeline"

    owner = getattr(instance, "created_by", None)
    emp_user_new = _employee_user_of(instance)

    if created:
        _grant_many(owner, ["view", "change"], instance)
        _grant_many(emp_user_new, ["view"], instance)
        return

    old_emp_id = getattr(instance, "_old_employee_id", None)
    if old_emp_id is not None and old_emp_id != getattr(instance, "employee_id", None):
        try:
            old_emp = models.Employee.objects.only("user_id").get(pk=old_emp_id)
            emp_user_old = getattr(old_emp, "user", None)
        except models.Employee.DoesNotExist:
            emp_user_old = None

        _remove_many(emp_user_old, ["view"], instance)
        _grant_many(emp_user_new, ["view"], instance)

