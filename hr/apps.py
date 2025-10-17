from django.apps import AppConfig


class HrConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "hr"

    def ready(self):
        # حمّل جميع الإشارات المسجّلة في hr/signals.py
        # مجرد الاستيراد يكفي لتفعيل @receiver
        from . import signals  # noqa: F401
