from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType

from .services import follow

# أدوات مساعدة عامة
def _safe_getattr(obj, name, default=None):
    try:
        return getattr(obj, name, default)
    except Exception:
        return default

def _auto_follow_for_target(target, *actors):
    """
    يحاول إضافة هؤلاء كمتابعين للسجل الهدف (User/Employee),
    يتجاهل أي قيمة None بأمان.
    """
    for actor in actors:
        if not actor:
            continue
        if actor.__class__.__name__ == "User":
            try:
                follow(target, user=actor)
            except Exception:
                pass
        else:
            # نفترض Employee
            try:
                follow(target, employee=actor)
            except Exception:
                pass


# -------- Performance: Task / Objective / Evaluation --------
try:
    from performance.models import Task, Objective, Evaluation
except Exception:  # pragma: no cover
    Task = Objective = Evaluation = None

if Task:
    @receiver(post_save, sender=Task)
    def task_auto_follow(sender, instance, created, **kwargs):
        # اجعل assignee متابعًا للـ Task
        _auto_follow_for_target(instance, _safe_getattr(instance, "assignee", None))

if Objective:
    @receiver(post_save, sender=Objective)
    def objective_auto_follow(sender, instance, created, **kwargs):
        # اجعل reviewer متابعًا للـ Objective
        _auto_follow_for_target(instance, _safe_getattr(instance, "reviewer", None))

if Evaluation:
    @receiver(post_save, sender=Evaluation)
    def evaluation_auto_follow(sender, instance, created, **kwargs):
        # اجعل employee/evaluator متابعين للتقييم
        _auto_follow_for_target(instance, _safe_getattr(instance, "employee", None))
        _auto_follow_for_target(instance, _safe_getattr(instance, "evaluator", None))


# -------- Assets: Asset holder --------
try:
    from assets.models import Asset
except Exception:  # pragma: no cover
    Asset = None

if Asset:
    @receiver(post_save, sender=Asset)
    def asset_auto_follow(sender, instance, created, **kwargs):
        # اجعل الحائز متابعًا للأصل
        _auto_follow_for_target(instance, _safe_getattr(instance, "holder", None))


# -------- Payroll: Payslip employee --------
try:
    from payroll.models import Payslip
except Exception:  # pragma: no cover
    Payslip = None

if Payslip:
    @receiver(post_save, sender=Payslip)
    def payslip_auto_follow(sender, instance, created, **kwargs):
        # اجعل الموظف متابعًا لقسيمته
        _auto_follow_for_target(instance, _safe_getattr(instance, "employee", None))
