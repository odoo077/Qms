from django.apps import AppConfig

class HrConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "hr"
    verbose_name = "HR"

    def ready(self):
        # مهم جدًا لتحميل مستقبلات الإشارات بعد جاهزية سجل التطبيقات
        from . import signals  # noqa
