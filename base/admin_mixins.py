# base/admin_mixins.py
# مزيّنات/ميكسنات عامة قابلة لإعادة الاستخدام في كل التطبيقات
from typing import Any, Sequence
from django.contrib import admin

def _unscoped_manager(model: type) -> Any:
    # يُرجع مديرًا غير مقيّد لعرض كل السجلات في الأدمن
    return getattr(model, "all_objects", model._base_manager)

class UnscopedAdminMixin:
    """
    يجعل الـ Admin يرى كل السجلات (بدون سكوب الشركات) ويعرض جميع خيارات FK/M2M.
    لا تستورد أي موديل هنا لتجنب الدوران.
    """
    def get_queryset(self, request):
        return _unscoped_manager(self.model).all()

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        Remote = db_field.remote_field.model
        kwargs.setdefault("queryset", _unscoped_manager(Remote).all())
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        Remote = db_field.remote_field.model
        kwargs.setdefault("queryset", _unscoped_manager(Remote).all())
        return super().formfield_for_manytomany(db_field, request, **kwargs)

class HideAuditFieldsMixin:
    """
    يُخفي حقول الأثر (created_by/updated_by/created_at/updated_at) إن وُجدت.
    آمن حتى لو لم تكن الحقول موجودة على الموديل.
    """
    AUDIT_FIELDS: Sequence[str] = ("created_by", "updated_by", "created_at", "updated_at")

    def get_exclude(self, request, obj=None):
        base_exclude = list(super().get_exclude(request, obj) or [])
        # أضف فقط الحقول الموجودة فعلاً على الموديل
        present = [f for f in self.AUDIT_FIELDS if f in {fld.name for fld in self.model._meta.get_fields()}]
        return list(set(base_exclude + present))

class ReadonlyAuditFieldsMixin:
    """
    يجعل حقول الأثر للقراءة فقط (لا يخفيها).
    """
    AUDIT_FIELDS: Sequence[str] = ("created_by", "updated_by", "created_at", "updated_at")

    def get_readonly_fields(self, request, obj=None):
        ro = list(super().get_readonly_fields(request, obj) or [])
        present = [f for f in self.AUDIT_FIELDS if f in {fld.name for fld in self.model._meta.get_fields()}]
        return list(set(ro + present))


class AppAdmin(UnscopedAdminMixin, HideAuditFieldsMixin, admin.ModelAdmin):
    pass
