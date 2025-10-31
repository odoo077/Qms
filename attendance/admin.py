from django.contrib import admin
from . import models
from base.admin_mixins import AppAdmin

@admin.register(models.AttendanceLog)
class AttendanceLogAdmin(AppAdmin):
    list_display = ("employee", "company", "kind", "ts", "source", "note")
    list_filter  = ("company", "kind", "source")
    search_fields = ("employee__name", "note")
    autocomplete_fields = ("employee", "company")
    ordering = ("-ts",)

@admin.register(models.AttendanceDay)
class AttendanceDayAdmin(AppAdmin):
    list_display = ("date", "employee", "company", "status",
                    "worked_minutes", "late_minutes", "early_leave_minutes", "overtime_minutes")
    list_filter  = ("company", "status", "weekday")
    search_fields = ("employee__name", "shift_name")
    autocomplete_fields = ("employee", "company")
    date_hierarchy = "date"
    ordering = ("-date",)
