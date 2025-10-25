# -*- coding: utf-8 -*-
from django.apps import AppConfig


class AssetsConfig(AppConfig):
    """
    الضبط العام لتطبيق الأصول
    - ربط signals
    """
    name = "assets"
    verbose_name = "Assets"

    def ready(self):
        # استيراد الإشعارات لربطها
        from . import signals  # noqa: F401
