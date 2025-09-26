from django.apps import AppConfig


class BaseConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "base"
    verbose_name = "Base (Odoo-like Core)"

    def ready(self):
        # ربط الإشارات
        from . import signals  # noqa: F401
