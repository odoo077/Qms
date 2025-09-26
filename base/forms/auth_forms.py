# base/forms/auth_forms.py
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError

User = get_user_model()

class RegisterForm(forms.ModelForm):
    """
    نموذج تسجيل يشمل كلمة المرور وتأكيدها.
    - يتحقق من تطابق كلمتي المرور.
    - يضبط is_active=False ليتم التفعيل عبر الإيميل (حسب منطق views لديك).
    """
    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        strip=False,
        min_length=8,
        help_text="Use at least 8 characters."
    )
    password2 = forms.CharField(
        label="Confirm password",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        strip=False,
    )

    class Meta:
        model = User
        fields = ["email", "username", "first_name", "last_name"]

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("This email is already registered.")
        return email

    def clean_password2(self):
        p1 = self.cleaned_data.get("password1")
        p2 = self.cleaned_data.get("password2")
        if not p1 or not p2:
            raise ValidationError("Please enter and confirm your password.")
        if p1 != p2:
            raise ValidationError("Passwords do not match.")
        return p2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = user.email.strip().lower()
        user.is_active = False  # سيتم التفعيل عبر رابط التفعيل
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class LoginForm(AuthenticationForm):
    # AuthenticationForm يستخدم name=username؛ نعرضه كحقل بريد فقط
    username = forms.EmailField(label="Email", widget=forms.EmailInput(attrs={"autocomplete": "email"}))
