from django.apps import AppConfig


class PerformanceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'performance'

    def ready(self):
        # Ensure signal handlers are registered
        from .signals import signals  # noqa: F401
