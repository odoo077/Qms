# base/apps.py
from django.apps import AppConfig
import logging


logger = logging.getLogger(__name__)


class BaseConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "base"
    verbose_name = "Base"

    def ready(self):
        # سجّل إشعارات/base signals (company context, ACL العامة، …)
        from . import signals  # noqa: F401

        # نحاول أيضًا تحميل إشعارات HR (مثلاً قواعد ACL الخاصة بالموظفين)
        # إذا لم يكن تطبيق hr أو ملف signals موجودًا لا نوقف النظام.
        try:
            import hr.signals  # noqa: F401
        except Exception:
            logger.debug("hr.signals could not be imported (optional).", exc_info=True)
