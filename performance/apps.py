# -*- coding: utf-8 -*-
from django.apps import AppConfig

class PerformanceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "performance"
    verbose_name = "Performance"

    def ready(self):
        # تفعيل الإشارات بتحميل ملف signals مرة واحدة
        from . import signals  # noqa: F401
