# base/apps.py
from django.apps import AppConfig

class BaseConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "base"
    verbose_name = "Base"

    def ready(self):
        # استيراد مباشر لملف signals كي تُسجَّل الديكورات @receiver
        from . import signals  # noqa: F401
