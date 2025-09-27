from django.apps import AppConfig

class HrConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "hr"

    def ready(self):
        # تأكد من تحميل الإشارات
        from .signals import employees  # noqa: F401
