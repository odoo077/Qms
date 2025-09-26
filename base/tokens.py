# base/tokens.py
from django.contrib.auth.tokens import PasswordResetTokenGenerator

class AccountActivationTokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user, timestamp):
        login_ts = "" if user.last_login is None else user.last_login.replace(microsecond=0, tzinfo=None)
        # ندخل email_verified ضمن الحساب لضمان بطلان الروابط بعد التفعيل
        return f"{user.pk}{user.is_active}{getattr(user, 'email_verified', False)}{login_ts}{timestamp}"

account_activation_token = AccountActivationTokenGenerator()
