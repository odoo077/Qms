from django.apps import AppConfig

class PerformanceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "performance"
    verbose_name = "Performance"

    def ready(self):
        # إشارات داخلية موجودة لديك (إعادة بناء المشاركين/إعادة احتساب المؤشرات)
        from .signals import signals  # noqa: F401
        # إشارات صلاحيات المجموعات
        from .signals import roles     # noqa: F401
        # إشارات منح الملكية
        from .signals import ownership # noqa: F401
