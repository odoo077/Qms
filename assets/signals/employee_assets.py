# assets/signals/employee_assets.py
from django.db.models.signals import post_delete
from django.dispatch import receiver
from assets.models import EmployeeAsset

@receiver(post_delete, sender=EmployeeAsset)
def reset_item_after_delete(sender, instance: EmployeeAsset, **kwargs):
    item = instance.item
    # لو لم يبقَ تسليم نشط، صفّر الحامل وأعد الحالة
    other = EmployeeAsset.objects.filter(item=item, is_active=True).values_list("employee_id", flat=True).first()
    item.current_employee_id = other or None
    if not other and item.status == "assigned":
        item.status = "in_stock"
    item.save(update_fields=["current_employee", "status"])
