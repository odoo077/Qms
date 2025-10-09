# base/security.py
from django.core.exceptions import PermissionDenied


# هذا الميكسن عام ويمكن استخدامه في أي تطبيق (assets/hr/skills …).
def user_has_action(user, obj_or_model, app_label: str, action_codename: str) -> bool:
    """
    تفحص صلاحية (model أو object). action_codename مثل: 'assign_item'، 'change_employee' ...
    """
    if not user.is_authenticated:
        return False
    if getattr(user, "is_superuser", False):
        return True
    perm = f"{app_label}.{action_codename}"
    # object-level أولاً إذا مرّرت كائنًا
    try:
        # إذا obj_or_model كائن فيه _meta
        if hasattr(obj_or_model, "_meta"):
            return user.has_perm(perm, obj_or_model) or user.has_perm(perm)
    except Exception:
        pass
    # وإلا اعتبره موديل-level
    return user.has_perm(perm)

class ObjectActionPermissionMixin:
    """مِكْسن يُستخدم في أي View لفرض صلاحية على كائن معيّن."""
    required_perm_app = None      # مثال 'assets'
    required_perm_codename = None # مثال 'assign_item'

    def check_perm(self, obj):
        if not self.required_perm_app or not self.required_perm_codename:
            return
        if not user_has_action(self.request.user, obj, self.required_perm_app, self.required_perm_codename):
            raise PermissionDenied("You do not have permission for this action.")
