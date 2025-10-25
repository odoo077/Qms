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

from guardian.shortcuts import assign_perm, remove_perm

from . import models


# ============================================================
# Helpers (Arabic comments)
# ============================================================

def _grant_if_user(user, codename: str, obj) -> None:
    """
    امنح صلاحية واحدة لمستخدم معيّن على كائن معيّن (Idempotent).
    - إن كان user=None نتجاهل بهدوء.
    """
    if user is None:
        return
    try:
        assign_perm(codename, user, obj)
    except Exception:
        # لا نكسر عملية الحفظ بسبب الأذونات
        pass


def _grant_many(user, perms: list[str], obj) -> None:
    """
    امنح مجموعة صلاحيات دفعة واحدة.
    """
    if user is None:
        return
    for p in perms:
        _grant_if_user(user, p, obj)


def _remove_many(user, perms: list[str], obj) -> None:
    """
    أزل مجموعة صلاحيات من مستخدم على كائن.
    """
    if user is None:
        return
    for p in perms:
        try:
            remove_perm(p, user, obj)
        except Exception:
            pass


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
        # مالك السجل (المنشئ) — عرض وتعديل (ويمكنك إضافة حذف إن أردت)
        _grant_many(owner, [VIEW, CHANGE, RATE], instance)

        # مستخدم الموظف — عرض فقط
        _grant_many(emp_user_new, [VIEW], instance)
        return

    # تحديث: إن تغيّر الموظف ننقل صلاحية العرض من القديم للجديد
    old_emp_id = getattr(instance, "_old_employee_id", None)
    if old_emp_id is not None and old_emp_id != getattr(instance, "employee_id", None):
        # المستخدم القديم للموظف (إن وجد)
        try:
            old_emp = models.Employee.objects.only("user_id").get(pk=old_emp_id)
            emp_user_old = getattr(old_emp, "user", None)
        except models.Employee.DoesNotExist:
            emp_user_old = None

        # أزل VIEW عن المستخدم القديم وأعطه للمستخدم الجديد
        _remove_many(emp_user_old, [VIEW], instance)
        _grant_many(emp_user_new, [VIEW], instance)


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
        _grant_many(owner, [VIEW, CHANGE], instance)
        _grant_many(emp_user_new, [VIEW], instance)
        return

    old_emp_id = getattr(instance, "_old_employee_id", None)
    if old_emp_id is not None and old_emp_id != getattr(instance, "employee_id", None):
        try:
            old_emp = models.Employee.objects.only("user_id").get(pk=old_emp_id)
            emp_user_old = getattr(old_emp, "user", None)
        except models.Employee.DoesNotExist:
            emp_user_old = None

        _remove_many(emp_user_old, [VIEW], instance)
        _grant_many(emp_user_new, [VIEW], instance)
