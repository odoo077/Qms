from django.contrib import admin
from .models import ChatterMessage, ChatterAttachment, ChatterFollower
from base.admin_mixins import AppAdmin


@admin.register(ChatterMessage)
class ChatterMessageAdmin(AppAdmin):
    list_display = ("id", "company", "target_ref", "author_user", "author_employee", "short_body", "created_at")
    list_filter = ("company", "content_type", "created_at")
    search_fields = ("body", "author_user__username", "author_employee__name")
    list_select_related = ("company", "author_user", "author_employee")
    autocomplete_fields = ("company", "author_user", "author_employee")

    def target_ref(self, obj):
        return f"{obj.content_type.model}#{obj.object_id}"

    def short_body(self, obj):
        txt = (obj.body or "")[:80]
        return txt + ("…" if len(obj.body or "") > 80 else "")

@admin.register(ChatterAttachment)
class ChatterAttachmentAdmin(AppAdmin):
    list_display = ("id", "message", "filename", "size")
    search_fields = ("filename",)
    list_select_related = ("message",)

@admin.register(ChatterFollower)
class ChatterFollowerAdmin(AppAdmin):
    list_display = ("id", "company", "target_ref", "user", "employee", "created_at")
    list_filter = ("company", "content_type")
    search_fields = ("user__username", "employee__name")
    list_select_related = ("company", "user", "employee")
    autocomplete_fields = ("company", "user", "employee")

    def target_ref(self, obj):
        return f"{obj.content_type.model}#{obj.object_id}"
