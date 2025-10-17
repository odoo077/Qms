# assets/apps.py
from django.apps import AppConfig


class AssetsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "assets"
    verbose_name = "Assets"

    def ready(self):
        # مجرد الاستيراد يفعّل جميع @receiver في assets/signals.py
        from . import signals  # noqa: F401
