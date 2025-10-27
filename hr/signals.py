# hr/signals.py
# ============================================================
# إشارات HR — Odoo-like
# - إنشاء/تعيين work_contact لكل Employee:
#     * إن كان مرتبطًا بمستخدم: نستخدم partner الخاص بالمستخدم.
#     * غير ذلك: إنشاء Partner (شخص) تحت Partner الشركة.
# - منح صلاحيات كائنية للمنشئ (owner-like) عند إنشاء الموظف.
# - أدوار HR الافتراضية (Groups) + أذونات.
# - حساب عدّادات الوظيفة (no_of_employee / expected_employees) عبر signals.
# ============================================================

from __future__ import annotations

from django.apps import apps
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models.signals import post_migrate, pre_save, post_save, post_delete
from django.dispatch import receiver

from base.acl_service import grant_access


# ------------------------------
# Helpers
# ------------------------------
def _get_model(app_label: str, model_name: str):
    return apps.get_model(app_label, model_name)


def _company_partner_for(company_id):
    Partner = _get_model("base", "Partner")
    return Partner.objects.filter(company_id=company_id, is_company=True).first()

def _flag_partner_employee(partner_id, value: bool):
    if not partner_id:
        return
    Partner = _get_model("base", "Partner")
    Partner.objects.filter(pk=partner_id).update(employee=value)


# ============================================================
# 1) Ensure work_contact (company-scoped) — Odoo-like (بدون تعديل شركة شريك موجود)
# ============================================================
@receiver(post_save, sender=_get_model("hr", "Employee"))
def ensure_employee_work_contact(sender, instance, created: bool, **kwargs):
    """
    منطق Odoo:
      - إن كان للموظف مستخدم: نستخدم بطاقة المستخدم فقط إن كانت بطاقة "عمل" داخل نفس الشركة.
      - إن اختلفت الشركة: لا نعدّل شركة شريك موجود إطلاقًا؛ ننشئ/نعيد استخدام بطاقة جديدة داخل شركة الموظف.
      - إن لم يكن للموظف مستخدم: ننشئ بطاقة "عمل" جديدة داخل شركة الموظف (إن لم نجد مناسبة).
      - نفعّل/نُعطّل Partner.employee وفق الاستخدام.
    """
    Partner = _get_model("base", "Partner")
    Emp = sender

    # لو عنده work_contact مسبقًا، فقط فعّل العلم وتحقق من القديم
    if instance.work_contact_id:
        # فعِّل العلم على البطاقة الحالية
        Partner.objects.filter(pk=instance.work_contact_id, employee=False).update(employee=True)
        # افحص البطاقة القديمة (إن تغيّرت)
        old_wc_id = getattr(instance, "_old_work_contact_id", None)
        if old_wc_id and old_wc_id != instance.work_contact_id:
            still_used = Emp.objects.filter(work_contact_id=old_wc_id).exists()
            if not still_used:
                Partner.objects.filter(pk=old_wc_id, employee=True).update(employee=False)
        return

    # لا يوجد work_contact — قرر ما المناسب
    user = getattr(instance, "user", None)
    user_partner_id = getattr(user, "partner_id", None)

    def _assign(partner_obj):
        Emp.objects.filter(pk=instance.pk).update(work_contact_id=partner_obj.id)
        instance.work_contact_id = partner_obj.id
        if getattr(partner_obj, "employee", None) is not True:
            Partner.objects.filter(pk=partner_obj.pk, employee=False).update(employee=True)

    if user_partner_id:
        # نستخدم بطاقة المستخدم فقط لو ضمن نفس الشركة
        try:
            up = Partner.objects.only("id", "company_id", "is_company").get(pk=user_partner_id)
        except Partner.DoesNotExist:
            up = None

        if up and getattr(up, "company_id", None) == instance.company_id:
            _assign(up)
            return
        # لو مختلفة الشركة: لا نعدّل up.company_id إطلاقًا — أنشئ/استخدم بطاقة جديدة داخل الشركة

    # أنشئ/أعد استخدام بطاقة "عمل" داخل شركة الموظف
    company_partner = _company_partner_for(instance.company_id)
    # ابحث بطاقة شخص باسم الموظف داخل نفس الشركة (إن أردت) — أو أنشئ مباشرةً
    new_wc = Partner.objects.create(
        name=instance.name,
        company_id=instance.company_id,
        is_company=False,
        type="contact",
        parent_id=getattr(company_partner, "id", None),
        employee=True,  # علم الموظف
    )
    _assign(new_wc)


# ------------------------------------------------------------
# منح صلاحيات كائنية للمنشئ (Owner-like) عند إنشاء Employee
# ------------------------------------------------------------
@receiver(post_save, sender=_get_model("hr", "Employee"))
def grant_owner_perms_employee(sender, instance, created: bool, **kwargs):
    """
    عند إنشاء موظف بواسطة مستخدم معيّن (created_by):
      - امنحه صلاحيات كائنية عبر نظام ACL: view + change + delete + approve.
        (approve هنا صلاحية كائنية من نظامنا، مختلفة عن صلاحية الموديل.)
    """
    if created and getattr(instance, "created_by", None):
        user = instance.created_by
        # نداء واحد يضبط الأعلام المطلوبة على ACE
        grant_access(
            instance,
            user=user,
            view=True,
            change=True,
            delete=True,
            approve=True,  # متاحة في ACL الجديد
        )


# ------------------------------------------------------------
# مزامنة work_contact مع user.partner + ضبط الأعلام بعد كل حفظ
# ------------------------------------------------------------
@receiver(post_save, sender=_get_model("hr", "Employee"))
def _sync_employee_work_contact_and_flags(sender, instance, created, **kwargs):
    """
    Odoo-like:
      1) إن كان الموظف مرتبطًا بمستخدم → work_contact = user.partner (إجباري).
         - لو يختلف الحالي → غيّر للـ user.partner.
         - سوِّ شركة user.partner إلى شركة الموظف إن اختلفت (لتمرير تحقق clean()).
      2) فعّل Partner.employee=True للـ work_contact الحالي.
      3) لو تغيّر work_contact → افحص القديم؛ إن لم يعد مستخدمًا → employee=False.
    """
    apps = sender._meta.apps
    Partner = apps.get_model("base", "Partner")
    Emp = sender

    user = getattr(instance, "user", None)
    up_id = getattr(user, "partner_id", None)

    # 1) فرض ربط work_contact = user.partner عند وجود مستخدم
    if up_id:
        # توحيد الشركة على بطاقة المستخدم (إن لزم)
        if instance.company_id and Partner.objects.filter(pk=up_id).exclude(company_id=instance.company_id).exists():
            Partner.objects.filter(pk=up_id).update(company_id=instance.company_id)

        # إن كان مختلفًا عمّا هو مخزّن الآن → حدّثه
        if instance.work_contact_id != up_id:
            old_wc_id = instance.work_contact_id
            # حدّث work_contact بدون إعادة استدعاء متسلسل لا نهائي
            Emp.objects.filter(pk=instance.pk).update(work_contact_id=up_id)
            instance.work_contact_id = up_id  # حدّث الكائن في الذاكرة

            # شطب العلم عن القديم لو لم يعد مستخدمًا
            if old_wc_id and not Emp.objects.filter(work_contact_id=old_wc_id).exists():
                _flag_partner_employee(old_wc_id, False)

    # 2) فعّل العلم على الحالي
    if instance.work_contact_id:
        _flag_partner_employee(instance.work_contact_id, True)

    # 3) لو تغيّر عن القديم (حتى لو لا يوجد مستخدم)
    old_wc_id = getattr(instance, "_old_work_contact_id", None)
    if old_wc_id and old_wc_id != instance.work_contact_id:
        if not Emp.objects.filter(work_contact_id=old_wc_id).exists():
            _flag_partner_employee(old_wc_id, False)


# ------------------------------------------------------------
# أدوار HR الافتراضية (Groups) + الأذونات
# ------------------------------------------------------------
@receiver(post_migrate)
def ensure_hr_roles(sender, **kwargs):
    """
    ينشئ مجموعات HR ويُسند لها الأذونات المناسبة.
    تُستدعى تلقائيًا بعد ترحيل تطبيق hr.
    """
    if getattr(sender, "name", None) != "hr":
        return

    Employee = _get_model("hr", "Employee")
    try:
        ct_emp = ContentType.objects.get_for_model(Employee)
    except Exception:
        return

    GROUPS = {
        "HR Managers": ("approve_employee", "view_private_fields", "view_employee", "change_employee"),
        "HR Officers": ("view_employee",),
    }

    for group_name, codenames in GROUPS.items():
        group, _ = Group.objects.get_or_create(name=group_name)
        for codename in codenames:
            try:
                perm = Permission.objects.get(codename=codename, content_type=ct_emp)
                group.permissions.add(perm)
            except Permission.DoesNotExist:
                continue


# ============================================================
# Job counters (Odoo-like compute/store)
# - no_of_employee / expected_employees
#   * تتحدث عند تغيّر موظف (إضافة/تعديل/حذف) أو تغيير no_of_recruitment للوظيفة
# ============================================================
def recompute_job_counters(job_id):
    if not job_id:
        return
    Employee = _get_model("hr", "Employee")
    Job = _get_model("hr", "Job")
    try:
        job = Job.objects.get(pk=job_id)
    except Job.DoesNotExist:
        return

    count = Employee.objects.filter(job_id=job_id, active=True).count()
    expected = count + (job.no_of_recruitment or 0)

    # نحدّث عبر update لتفادي إشعال post_save من جديد بلا داعٍ
    Job.objects.filter(pk=job_id).update(
        no_of_employee=count,
        expected_employees=expected,
    )


@receiver(pre_save, sender=_get_model("hr", "Employee"))
def _employee_capture_old_vals(sender, instance, **kwargs):
    """
    نلتقط القيم القديمة لاستخدامها بعد الحفظ:
    - job_id / active
    - user_id / work_contact_id  (كي نعرف التغير ونشيل/نضيف أعلام partner.employee)
    """
    if instance.pk:
        try:
            old = sender.objects.only("job_id", "active", "user_id", "work_contact_id").get(pk=instance.pk)
            instance._old_job_id = old.job_id
            instance._old_active = old.active
            instance._old_user_id = old.user_id
            instance._old_work_contact_id = old.work_contact_id
        except sender.DoesNotExist:
            instance._old_job_id = instance._old_active = instance._old_user_id = instance._old_work_contact_id = None
    else:
        instance._old_job_id = instance._old_active = instance._old_user_id = instance._old_work_contact_id = None


@receiver(post_save, sender=_get_model("hr", "Employee"))
def _employee_recompute_jobs_after_save(sender, instance, created, **kwargs):
    new_job_id = instance.job_id
    old_job_id = getattr(instance, "_old_job_id", None)
    old_active = getattr(instance, "_old_active", None)

    def _on_commit():
        if created:
            recompute_job_counters(new_job_id)
        else:
            changed_job = (old_job_id != new_job_id)
            changed_active = (old_active is not None and old_active != instance.active)
            if changed_job or changed_active:
                if old_job_id and old_job_id != new_job_id:
                    recompute_job_counters(old_job_id)
                recompute_job_counters(new_job_id)

    transaction.on_commit(_on_commit)


@receiver(post_delete, sender=_get_model("hr", "Employee"))
def _employee_recompute_jobs_after_delete(sender, instance, **kwargs):
    def _on_commit():
        recompute_job_counters(instance.job_id)
    transaction.on_commit(_on_commit)


@receiver(post_save, sender=_get_model("hr", "Job"))
def _job_recompute_expected_on_recruitment(sender, instance, **kwargs):
    """لو تغيّر no_of_recruitment نحدّث expected_employees."""
    def _on_commit():
        Job = _get_model("hr", "Job")
        expected = (instance.no_of_employee or 0) + (instance.no_of_recruitment or 0)
        Job.objects.filter(pk=instance.pk).update(expected_employees=expected)
    transaction.on_commit(_on_commit)


@receiver(post_save, sender=_get_model("hr", "Employee"))
def _employee_flag_partner_on_save(sender, instance, created, **kwargs):
    """
    Odoo-like:
      - فعّل Partner.employee=True للـ work_contact الحالي.
      - لو تغيّر work_contact، افحص الشريك القديم؛
        إن لم يعد مستخدمًا من أي موظف → ألغِ العلم employee=False.
    """
    Partner = _get_model("base", "Partner")
    Emp = sender

    # 1) فعّل العلم على الشريك الحالي (إن وُجد)
    if instance.work_contact_id:
        Partner.objects.filter(pk=instance.work_contact_id, employee=False).update(employee=True)

    # 2) إن تغيّر الـ work_contact: نزع العلم من القديم إن لم يعد مستخدمًا
    old_id = getattr(instance, "_old_work_contact_id", None)
    new_id = instance.work_contact_id
    if old_id and old_id != new_id:
        still_used = Emp.objects.filter(work_contact_id=old_id).exists()
        if not still_used:
            Partner.objects.filter(pk=old_id, employee=True).update(employee=False)


@receiver(post_delete, sender=_get_model("hr", "Employee"))
def _employee_unflag_partner_on_delete(sender, instance, **kwargs):
    """
    عند حذف الموظف:
      - إن لم يعد work_contact مستخدمًا من أي موظف → employee=False على بطاقة الشريك.
    """
    if not instance.work_contact_id:
        return
    Emp = sender
    Partner = _get_model("base", "Partner")
    still_used = Emp.objects.filter(work_contact_id=instance.work_contact_id).exists()
    if not still_used:
        Partner.objects.filter(pk=instance.work_contact_id, employee=True).update(employee=False)


@receiver(post_delete, sender=_get_model("hr", "Employee"))
def _unflag_partner_on_employee_delete(sender, instance, **kwargs):
    wc_id = getattr(instance, "work_contact_id", None)
    if not wc_id:
        return
    if not sender.objects.filter(work_contact_id=wc_id).exists():
        _flag_partner_employee(wc_id, False)
