# performance/apps.py
from django.apps import AppConfig


class PerformanceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "performance"
    verbose_name = "Performance"

    def ready(self):
        # تفعيل إشارات التطبيق بتحميل ملف signals مرة واحدة
        # ملاحظة: لا تنقل هذا الاستيراد لأعلى الملف كي لا يحدث
        # تحميل مبكر قبل تهيئة سجل التطبيقات.
        from . import signals  # noqa: F401
        # أو يمكنك استخدام: import performance.signals
