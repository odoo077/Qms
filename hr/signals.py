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

from base.acl_service import grant_access, apply_default_acl, revoke_access


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

@receiver(
    post_save,
    sender=_get_model("hr", "Employee"),
    dispatch_uid="hr.ensure_employee_work_contact.v3",
)
def ensure_employee_work_contact(sender, instance, created: bool, **kwargs):
    """
    Idempotent & single-source-of-truth:
      - إن كان مرتبطًا بمستخدم → استخدم user.partner دائمًا ووحّد الشركة.
      - إن لم يكن → أعد استخدام بطاقة مناسبة داخل الشركة أو أنشئ واحدة مرة واحدة فقط.
      - حدّث أعلام Partner.employee (إضافة/إزالة) عند التبديل.
    """
    Partner = _get_model("base", "Partner")
    Emp = sender

    # حارس تكرار داخل نفس الطلب/الحفظ لمنع إعادة التنفيذ
    if getattr(instance, "_work_contact_ensured", False):
        return
    setattr(instance, "_work_contact_ensured", True)

    # اقرأ قيمة work_contact الحالية من قاعدة البيانات (حتى لو لم يمرره الفورم)
    db_wc_id = None
    if instance.pk:
        db_wc_id = Emp.objects.filter(pk=instance.pk).values_list("work_contact_id", flat=True).first()

    # لو مرتبط بمستخدم وله partner → هذا هو المصدر الحقيقي (أولوية قصوى مثل Odoo)
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
            company_partner = _company_partner_for(instance.company_id)
            updates["parent_id"] = getattr(company_partner, "id", None)
        if updates:
            Partner.objects.filter(pk=up_id).update(**updates)

        _use_partner(up_id)
        return

    # لا يوجد user.partner:
    # إن كان الفورم/الموديل قد حدده أصلاً على الـ instance → لا ننشئ ولا نبدل، فقط نضمن العلم
    if getattr(instance, "work_contact_id", None):
        _flag_partner_employee(instance.work_contact_id, True)
        return

    # إن كان هناك work_contact محفوظ في قاعدة البيانات للسجل الحالي → أعد تفعيل العلم وتوقف
    if db_wc_id:
        Partner.objects.filter(pk=db_wc_id, employee=False).update(employee=True)
        return

    # لا تُنشئ أي جهة اتصال جديدة عند تعديل/فتح السجل؛ الإنشاء لأول مرة فقط
    if not created:
        return

    # محاولة إعادة استخدام بطاقة داخل الشركة (تجاهل parent_id أولاً لتفادي التذبذب)
    from django.db.models import Q
    company_partner = _company_partner_for(instance.company_id)
    parent_id = getattr(company_partner, "id", None)

    # ➊ جرّب إعادة الاستخدام بالاسم داخل نفس الشركة بغضّ النظر عن parent
    reuse = Partner.objects.filter(
        company_id=instance.company_id,
        is_company=False,
    ).filter(
        Q(type="contact") | Q(type__isnull=True)
    ).filter(
        Q(name=instance.name) | Q(display_name=instance.name)
    ).order_by("id").first()

    # ➊ إعادة الاستخدام أو الإنشاء (مرة واحدة فقط عند created=True)
    partner = reuse
    if not partner:
        partner = Partner.objects.create(
            company_id=instance.company_id,
            is_company=False,
            name=instance.name,
            parent_id=parent_id,
            employee=True,
            type="contact",
            display_name=instance.name,
        )

    partner_id = partner.id

    # --- تثبيت الثوابت: شخص + نفس الشركة + parent = Company.partner إن وُجد (Odoo-like HR) ---
    updates = {
        "is_company": False,
        "company_type": "person",
        "type": "contact",
        "company_id": instance.company_id,
        "parent_id": parent_id,
    }
    # لا نكتب None صراحة
    updates = {k: v for k, v in updates.items() if v is not None}

    # تأكيد display_name إن كان فارغًا
    if not getattr(partner, "display_name", None):
        updates["display_name"] = instance.name

    # تفعيل علم employee على الشريك الحالي
    if not getattr(partner, "employee", False):
        updates["employee"] = True

    if updates:
        Partner.objects.filter(pk=partner_id).update(**updates)

    _use_partner(partner_id)
    return


# ------------------------------------------------------------
# منح صلاحيات كائنية للمنشئ (Owner-like) عند إنشاء Employee
# ------------------------------------------------------------
@receiver(post_save, sender=_get_model("hr", "Employee"))
def grant_owner_perms_employee(sender, instance, created: bool, **kwargs):
    """
    طبّق السياسة الافتراضية المركزية (مالك + HR-Manager + مدير القسم).
    """
    apply_default_acl(instance)



@receiver(post_save, sender=_get_model("hr", "Employee"))
def _employee_fix_acl_on_department_change(sender, instance, created, **kwargs):
    """
    لو تغيّر القسم، اسحب صلاحيات المدير القديم من هذا السجل فقط.
    ثم طبّق السياسة الافتراضية (ستمنح المدير الجديد تلقائيًا).
    """
    old_dept_id = getattr(instance, "_old_department_id", None)
    new_dept_id = getattr(instance, "department_id", None)

    if old_dept_id and old_dept_id != new_dept_id:
        # مدير القسم القديم → user
        Department = _get_model("hr", "Department")
        old_dept = Department._base_manager.only("manager_id").filter(pk=old_dept_id).first()
        if old_dept and getattr(old_dept, "manager_id", None):
            old_mgr_emp = old_dept.manager
            if getattr(old_mgr_emp, "user_id", None):
                # اسحب الصلاحيات من المستخدم القديم فقط
                revoke_access(instance, user=old_mgr_emp.user)

    # ثم ضمّن أن السياسة الافتراضية مفعّلة بعد أي تغيير
    apply_default_acl(instance)


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
            old = sender.objects.only(
                "job_id", "active", "user_id", "work_contact_id", "department_id"
            ).get(pk=instance.pk)
            instance._old_job_id = old.job_id
            instance._old_active = old.active
            instance._old_user_id = old.user_id
            instance._old_work_contact_id = old.work_contact_id
            instance._old_department_id = old.department_id  # NEW
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
