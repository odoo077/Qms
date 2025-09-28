# hr/signals/employees.py
from django.dispatch import receiver
from django.db import transaction
from django.apps import apps
from django.db.models.signals import pre_save, post_save, post_delete
from django.db.models import Q

Employee = apps.get_model("hr", "Employee")
Partner = apps.get_model("base", "Partner")

@receiver(post_save, sender=Employee)
def ensure_employee_work_contact(sender, instance: Employee, created, **kwargs):
    """
    منطق Odoo: كل موظف يجب أن يملك work_contact.
    - لو مرتبط بـ User → استخدم partner الخاص بالمستخدم (مع ضبط الشركة).
    - وإلا أنشئ Partner تحت Partner الشركة.
    """
    if instance.work_contact_id:
        return

    def _assign(partner):
        # تأكد من الشركة
        if getattr(partner, "company_id", None) != instance.company_id and hasattr(partner, "company_id"):
            partner.company_id = instance.company_id
            partner.save(update_fields=["company"])
        # اربط وأكمل الحقول المشتقة
        instance.work_contact_id = partner.id
        updates = ["work_contact"]
        if not instance.work_email and getattr(partner, "email", ""):
            instance.work_email = partner.email; updates.append("work_email")
        if not instance.work_phone and getattr(partner, "phone", ""):
            instance.work_phone = partner.phone; updates.append("work_phone")
        instance.save(update_fields=updates)

    def _do():
        user = getattr(instance, "user", None)
        if user and getattr(user, "partner", None):
            _assign(user.partner)
            return
        # أنشئ Partner جديد للموظف تحت Partner الشركة
        company_partner = None
        try:
            company_partner = Partner.objects.filter(
                company_id=instance.company_id, is_company=True
            ).first()
        except Exception:
            pass
        p = Partner.objects.create(
            name=instance.name,
            is_company=False,
            company_id=instance.company_id,
            parent=company_partner,
            type="contact",
            company_type="person",
            employee=True,
        )
        _assign(p)

    # سجّل التنفيذ بعد نجاح الـ commit؛ وإن لم نكن داخل atomic نفذ فورًا
    try:
        transaction.on_commit(_do)
    except Exception:
        _do()

@receiver(pre_save, sender=Employee)
def _capture_old_department_and_active(sender, instance: Employee, **kwargs):
    """
    قبل الحفظ: التقط القسم/الحالة القديمة لتحديث العد لاحقاً.
    نخزنها مؤقتاً على instance (لن تُحفظ DB).
    """
    if not instance.pk:
        instance.__old_department_id = None
        instance.__old_active = None
        return
    try:
        old = Employee.objects.all_companies().only("department_id", "active").get(pk=instance.pk)
        instance.__old_department_id = old.department_id
        instance.__old_active = old.active
    except Employee.DoesNotExist:
        instance.__old_department_id = None
        instance.__old_active = None

def _recompute_dept_counts(*dept_ids):
    from django.apps import apps
    Department = apps.get_model("hr", "Department")
    for did in filter(None, set(dept_ids)):
        try:
            dept = Department.all_objects.get(pk=did)  # بلا سكوب
            total = dept.members.filter(active=True).count()
            if total != dept.total_employee:
                dept.total_employee = total
                dept.save(update_fields=["total_employee"])
        except Department.DoesNotExist:
            pass

@receiver(post_save, sender=Employee)
def _update_counts_on_employee_save(sender, instance: Employee, created, **kwargs):
    """
    بعد الحفظ: حدّث العدّ عند الحالات:
    - إنشاء موظف Active ومربوط بقسم
    - تغيير department
    - تغيير active
    """
    old_dep = getattr(instance, "__old_department_id", None)
    old_active = getattr(instance, "__old_active", None)
    new_dep = instance.department_id
    new_active = instance.active

    # حالات تستوجب تحديث
    touched = False
    if created and new_active and new_dep:
        _recompute_dept_counts(new_dep)
        touched = True
    if (old_dep != new_dep) or (old_active != new_active):
        _recompute_dept_counts(old_dep, new_dep)
        touched = True

    # نظّف المتغيرات المؤقتة
    if touched:
        for attr in ("__old_department_id", "__old_active"):
            if hasattr(instance, attr):
                delattr(instance, attr)

@receiver(post_delete, sender=Employee)
def _update_counts_on_employee_delete(sender, instance: Employee, **kwargs):
    """عند حذف الموظف، حدّث عدّ قسمه إن وُجد."""
    if instance.department_id:
        _recompute_dept_counts(instance.department_id)