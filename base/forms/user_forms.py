# base/forms/user_forms.py
from django import forms
from django.contrib.auth.forms import ReadOnlyPasswordHashField
from ..models import User

class UserCreateForm(forms.ModelForm):
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Confirm password", widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ("email", "username", "first_name", "last_name", "company", "companies")

    def clean_password2(self):
        p1 = self.cleaned_data.get("password1")
        p2 = self.cleaned_data.get("password2")
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Passwords don't match.")
        return p2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
            self.save_m2m()
        return user


class UserUpdateForm(forms.ModelForm):
    password = ReadOnlyPasswordHashField(help_text="Raw passwords are not stored. Use the admin form to change it.")

    class Meta:
        model = User
        fields = (
            "email", "username", "first_name", "last_name",
            "company", "companies",
            "is_staff", "is_superuser", "is_active", "active"
        )


class ProfileEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name")
