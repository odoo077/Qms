# ============================================================
# Django Admin Mixins
# ------------------------------------------------------------
# مزيّنات/ميكسنات عامة قابلة لإعادة الاستخدام في كل التطبيقات
# تُستخدم لتحسين تجربة Django Admin في بيئة متعددة الشركات
# ============================================================

from typing import Any, Sequence

from django.contrib import admin


# ============================================================
# Internal Helpers
# ============================================================

def _unscoped_manager(model: type) -> Any:
    """
    Return an unscoped manager for admin usage.

    - If the model defines `all_objects`, it is used
    - Otherwise fallback to Django's base manager
    """
    return getattr(model, "all_objects", model._base_manager)


# ============================================================
# Admin Mixins
# ============================================================

class UnscopedAdminMixin:
    """
    Make Django Admin unscoped (Odoo-like behavior).

    Effects:
    - Admin sees all records (no company scope)
    - ForeignKey and ManyToMany fields show all possible choices

    Notes:
    - No models are imported here to avoid circular imports
    """

    def get_queryset(self, request):
        return _unscoped_manager(self.model).all()

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        remote_model = db_field.remote_field.model
        kwargs.setdefault(
            "queryset",
            _unscoped_manager(remote_model).all(),
        )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        remote_model = db_field.remote_field.model
        kwargs.setdefault(
            "queryset",
            _unscoped_manager(remote_model).all(),
        )
        return super().formfield_for_manytomany(db_field, request, **kwargs)


class HideAuditFieldsMixin:
    """
    Hide audit fields in Django Admin if they exist on the model.

    Fields handled safely:
    - created_by
    - updated_by
    - created_at
    - updated_at

    Safe to use even if the model does not define these fields.
    """

    AUDIT_FIELDS: Sequence[str] = (
        "created_by",
        "updated_by",
        "created_at",
        "updated_at",
    )

    def get_exclude(self, request, obj=None):
        base_exclude = list(super().get_exclude(request, obj) or [])

        model_fields = {field.name for field in self.model._meta.get_fields()}
        present_fields = [f for f in self.AUDIT_FIELDS if f in model_fields]

        return list(set(base_exclude + present_fields))


class ReadonlyAuditFieldsMixin:
    """
    Make audit fields read-only in Django Admin (without hiding them).
    """

    AUDIT_FIELDS: Sequence[str] = (
        "created_by",
        "updated_by",
        "created_at",
        "updated_at",
    )

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj) or [])

        model_fields = {field.name for field in self.model._meta.get_fields()}
        present_fields = [f for f in self.AUDIT_FIELDS if f in model_fields]

        return list(set(readonly + present_fields))


# ============================================================
# Base Admin Class
# ============================================================

class AppAdmin(UnscopedAdminMixin, HideAuditFieldsMixin, admin.ModelAdmin):
    """
    Base Admin class for all applications.

    Defaults:
    - Unscoped admin behavior
    - Audit fields hidden if present
    """
    pass
