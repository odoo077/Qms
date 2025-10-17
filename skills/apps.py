# skills/apps.py
from django.apps import AppConfig


class SkillsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "skills"
    verbose_name = "Skills"

    def ready(self):
        # مجرّد الاستيراد يفعّل جميع @receiver الموجودة في skills/signals.py
        from . import signals  # noqa: F401
