from django.apps import AppConfig

class ChatterConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "chatter"
    verbose_name = "Chatter"

    def ready(self):
        # ربط الإشارات
        from . import signals  # noqa
