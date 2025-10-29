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
    Idempotent & single-source-of-truth:
      - إن كان مرتبطًا بمستخدم → استخدم user.partner دائمًا ووحّد الشركة.
      - إن لم يكن → أعد استخدام بطاقة مناسبة داخل الشركة أو أنشئ واحدة مرة واحدة فقط.
      - حدّث أعلام Partner.employee (إضافة/إزالة) عند التبديل.
    """
    Partner = _get_model("base", "Partner")
    Emp = sender

    # اقرأ قيمة work_contact الحالية من قاعدة البيانات (حتى لو لم يمررها الفورم)
    db_wc_id = None
    if instance.pk:
        db_wc_id = Emp.objects.filter(pk=instance.pk).values_list("work_contact_id", flat=True).first()

    # لو مرتبط بمستخدم وله partner
    user = getattr(instance, "user", None)
    up_id = getattr(user, "partner_id", None)

    def _use_partner(pid: int):
        """اربط هذا الشريك كـ work_contact + اضبط أعلام employee بنظافة."""
        old_id = db_wc_id
        if old_id != pid:
            Emp.objects.filter(pk=instance.pk).update(work_contact_id=pid)
            instance.work_contact_id = pid
            # أزل العلم عن القديم إن لم يعد مستخدمًا
            if old_id and old_id != pid and not Emp.objects.filter(work_contact_id=old_id).exists():
                Partner.objects.filter(pk=old_id, employee=True).update(employee=False)
        # فعّل العلم على الحالي
        Partner.objects.filter(pk=pid, employee=False).update(employee=True)

    if up_id:
        # وحِّد شركة user.partner مع شركة الموظف (وأعد وضعه تحت Partner الشركة إن توفر)
        updates = {}
        if instance.company_id and Partner.objects.filter(pk=up_id).exclude(company_id=instance.company_id).exists():
            updates["company_id"] = instance.company_id
            # ضع parent إلى Partner الشركة (إن وجد) لمطابقة شجرة Odoo
            company_partner = _company_partner_for(instance.company_id)
            updates["parent_id"] = getattr(company_partner, "id", None)
        if updates:
            Partner.objects.filter(pk=up_id).update(**updates)

        _use_partner(up_id)
        return

    # لا يوجد user.partner:
    if db_wc_id:
        # أعد فقط تفعيل العلم وتوقف — لا إنشاء جديد
        Partner.objects.filter(pk=db_wc_id, employee=False).update(employee=True)
        return

    # محاولة إعادة استخدام بطاقة داخل الشركة (نفس الاسم وتحت Partner الشركة)
    company_partner = _company_partner_for(instance.company_id)
    reuse = Partner.objects.filter(
        company_id=instance.company_id,
        parent_id=getattr(company_partner, "id", None),
        type="contact",
        name=instance.name,
        is_company=False,
    ).order_by("id").first()

    if reuse:
        _use_partner(reuse.id)
        return

    # إنشاء بطاقة جديدة مرة واحدة فقط
    new_p = Partner.objects.create(
        name=instance.name,
        company_id=instance.company_id,
        is_company=False,
        type="contact",
        parent_id=getattr(company_partner, "id", None),
        employee=True,
    )
    _use_partner(new_p.id)



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
