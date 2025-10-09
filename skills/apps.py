# skills/apps.py
from django.apps import AppConfig


class SkillsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "skills"
    verbose_name = "Skills"

    def ready(self):
        """
        عند تشغيل المشروع يقوم باستيراد وحدات الإشارات (signals)
        لكي تُسجَّل جميع الـ receivers:
        - skill_signals: إشارات مستويات المهارة.
        - employee_skill_signals: تحقق قبل حفظ مهارة موظف.
        - ownership: منح صلاحيات المالك على السجل الجديد.
        - roles: إنشاء/تأكيد مجموعات وصلاحيات التطبيق بعد الترحيل.
        """
        # مجرد الاستيراد يكفي لتوصيل الإشارات
        from .signals import skill_signals  # noqa: F401
        from .signals import employee_skill_signals  # noqa: F401
        from .signals import ownership  # noqa: F401
        from .signals import roles  # noqa: F401
