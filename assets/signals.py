# -*- coding: utf-8 -*-
"""
إشعارات (Signals) للتكامل مع نظام ACL المخصّص ومنطق الاتساق
- على الإنشاء: تعيين المنشئ كصاحب صلاحيات على الكائن
- على تغيير الشركة: ضمان اتساق الشركة مع العلاقات التابعة (Category/Assignment)
"""

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.utils import timezone

from . import models as m
from . import services as s

User = get_user_model()


@receiver(pre_save, sender=m.AssetCategory)
def _cat_update_parent_path(sender, instance: m.AssetCategory, **kwargs):
    if instance.parent_id:
        # اجلب parent_path من DB لضمان التوفر
        try:
            parent = m.AssetCategory.objects.only("id", "parent_path").get(pk=instance.parent_id)
            prefix = parent.parent_path or ""
        except m.AssetCategory.DoesNotExist:
            prefix = ""
        instance.parent_path = f"{prefix}{instance.parent_id}/"
    else:
        instance.parent_path = ""


@receiver(post_save, sender=m.Asset)
def _asset_grant_creator_object_perms(sender, instance: m.Asset, created: bool, **kwargs):
    """
    عند إنشاء أصل:
    - امنح المنشئ صلاحيات الكائن الافتراضية (إن وُجد)
    يمكنك توسيع هذا المنح ليشمل أدوار الشركة أو مدراء القسم...
    """
    if created and instance.created_by_id:
        try:
            s.grant_default_object_perms(instance, users=[instance.created_by])
        except Exception:
            # لا نفشل المعاملة بسبب منح صلاحية؛ سجّل لاحقًا إن أردت
            pass


@receiver(pre_save, sender=m.Asset)
def _asset_company_consistency(sender, instance: m.Asset, **kwargs):
    """
    ضمان الاتساق عند تغيير الشركة:
    - إن تغيّر company، ننظف العلاقات التي لا تتبع الشركة الجديدة (holder/department/category).
    - الهدف محاكاة أسلوب Odoo في تجاوز التعارضات بدل رفع أخطاء تخريبية.
    """
    if not instance.pk:
        return
    try:
        old: m.Asset = m.Asset.objects.get(pk=instance.pk)
        # حفظ القيم القديمة لاستخدامها بعد الحفظ
        instance._old_holder_id = old.holder_id
        instance._old_status = old.status

        # ✅ إذا غيّر المستخدم الحالة إلى غير "Assigned" ننظف الحامل لضمان الاتساق
        if instance.status != m.Asset.Status.ASSIGNED and instance.holder_id:
            instance.holder = None


    except m.Asset.DoesNotExist:
        return

    if old.company_id != instance.company_id:
        # إن تغيّرت الشركة:
        # 1) category من شركة أخرى؟ أزلها
        if instance.category_id and instance.category and instance.category.company_id and \
           instance.category.company_id != instance.company_id:
            instance.category = None

        # 2) department من شركة أخرى؟ أزلها
        if instance.department_id and instance.department and instance.department.company_id and \
           instance.department.company_id != instance.company_id:
            instance.department = None

        # 3) holder من شركة أخرى؟ ألغِ إسناده
        if instance.holder_id and instance.holder and instance.holder.company_id and \
           instance.holder.company_id != instance.company_id:
            instance.holder = None
            instance.status = m.Asset.Status.AVAILABLE


@receiver(post_save, sender=m.Asset)
def _asset_auto_assignment_on_holder_change(sender, instance: m.Asset, created: bool, **kwargs):
    """
    منطق تلقائي لإنشاء/إغلاق العهدة (AssetAssignment):
    - على الإنشاء أو التحديث: إذا تغيّر holder أو status، نغلق العهدة السابقة وننشئ عهدة جديدة عند الاقتضاء.
    """
    today = timezone.now().date()

    old_holder_id = getattr(instance, "_old_holder_id", None)
    old_status = getattr(instance, "_old_status", None)
    new_holder_id = instance.holder_id
    new_status = instance.status

    # نتحرك فقط عند الإنشاء أو تغيّر الحقول ذات الصلة
    changed = created or (old_holder_id != new_holder_id) or (old_status != new_status)
    if not changed:
        return

    # 1) إغلاق العهدة المفتوحة للموظف السابق عند تغيّر الحائز أو تغيّر الحالة لغير Assigned
    if old_holder_id:
        open_qs = m.AssetAssignment.objects.filter(
            asset=instance,
            employee_id=old_holder_id,
            date_to__isnull=True,
            active=True,
        )
        if (new_holder_id != old_holder_id) or (new_status != m.Asset.Status.ASSIGNED):
            open_qs.update(date_to=today)

    # 2) إنشاء عهدة جديدة إذا لدينا حائز جديد والحالة Assigned ولا توجد عهدة مفتوحة له أصلًا
    if new_holder_id and (new_status == m.Asset.Status.ASSIGNED):
        exists = m.AssetAssignment.objects.filter(
            asset=instance,
            employee_id=new_holder_id,
            date_to__isnull=True,
            active=True,
        ).exists()
        if not exists:
            m.AssetAssignment.objects.create(
                asset=instance,
                employee_id=new_holder_id,
                company=instance.company,
                date_from=today,
                note="Auto-created from Asset change",
            )



@receiver(pre_save, sender=m.AssetAssignment)
def _ensure_assignment_company_consistency(sender, instance: m.AssetAssignment, **kwargs):
    """
    ضمان اتساق الشركة في AssetAssignment:
    إذا كانت الشركة لا تطابق شركة الأصل، يتم تعديلها تلقائيًا.
    (محاكاة لمنطق Odoo الذي يفرض company consistency بدون أخطاء).
    """
    if instance.asset_id and instance.asset.company_id:
        instance.company_id = instance.asset.company_id
