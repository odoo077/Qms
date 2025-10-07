# # base/forms/forms.py
# from django.contrib.auth.forms import ReadOnlyPasswordHashField
# from ..models import User, Partner, Company
# from django import forms
# from django.contrib.auth.forms import AuthenticationForm
# from django.contrib.auth import get_user_model
#
# class UserCreateForm(forms.ModelForm):
#     password1 = forms.CharField(label="Password", widget=forms.PasswordInput)
#     password2 = forms.CharField(label="Confirm password", widget=forms.PasswordInput)
#
#     class Meta:
#         model = User
#         fields = ("email", "username", "first_name", "last_name", "company", "companies", "partner")
#
#     def clean_password2(self):
#         p1 = self.cleaned_data.get("password1")
#         p2 = self.cleaned_data.get("password2")
#         if p1 and p2 and p1 != p2:
#             raise forms.ValidationError("Passwords don't match.")
#         return p2
#
#     def save(self, commit=True):
#         user = super().save(commit=False)
#         user.set_password(self.cleaned_data["password1"])
#         if commit:
#             user.save()
#             self.save_m2m()
#         return user
#
#
# class UserUpdateForm(forms.ModelForm):
#     password = ReadOnlyPasswordHashField(help_text="Raw passwords are not stored. Use the admin form to change it.")
#
#     class Meta:
#         model = User
#         fields = (
#             "email", "username", "first_name", "last_name",
#             "company", "companies", "partner",
#             "is_staff", "is_superuser", "is_active", "active"
#         )
#
#
# class PartnerForm(forms.ModelForm):
#     class Meta:
#         model = Partner
#         fields = (
#             "name", "is_company", "company_type", "type", "parent", "company",
#             "email", "phone", "website", "vat", "company_registry", "categories", "employee",
#             "street", "street2", "zip", "city", "state", "country",
#         )
#
#
# class CompanySwitchForm(forms.Form):
#     def __init__(self, *args, user=None, current_ids=None, **kwargs):
#         super().__init__(*args, **kwargs)
#         qs = user.companies.all() if user else Company.objects.none()
#         self.fields["companies"] = forms.ModelMultipleChoiceField(
#             queryset=qs,
#             required=True,
#             label="Companies",
#             help_text="Select one or more companies to work under.",
#             widget=forms.SelectMultiple(attrs={"class": "select select-bordered w-full", "size": 6}),
#         )
#         # اختيار افتراضي: الشركات المفعّلة من الجلسة أو الشركة الافتراضية
#         if current_ids:
#             self.initial["companies"] = qs.filter(id__in=current_ids)
#
#
#
# User = get_user_model()
#
# class RegisterForm(forms.ModelForm):
#     """
#     نموذج تسجيل يشمل كلمة المرور وتأكيدها.
#     - يتحقق من تطابق كلمتي المرور.
#     - يضبط is_active=False ليتم التفعيل عبر الإيميل (حسب منطق views لديك).
#     """
#     password1 = forms.CharField(
#         label="Password",
#         widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
#         strip=False,
#         min_length=8,
#         help_text="Use at least 8 characters."
#     )
#     password2 = forms.CharField(
#         label="Confirm password",
#         widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
#         strip=False,
#     )
#
#     class Meta:
#         model = User
#         fields = ["email", "username", "first_name", "last_name"]
#
#     def clean_email(self):
#         email = (self.cleaned_data.get("email") or "").strip().lower()
#         if User.objects.filter(email__iexact=email).exists():
#             raise ValidationError("This email is already registered.")
#         return email
#
#     def clean_password2(self):
#         p1 = self.cleaned_data.get("password1")
#         p2 = self.cleaned_data.get("password2")
#         if not p1 or not p2:
#             raise ValidationError("Please enter and confirm your password.")
#         if p1 != p2:
#             raise ValidationError("Passwords do not match.")
#         return p2
#
#     def save(self, commit=True):
#         user = super().save(commit=False)
#         # المستخدم يعتمد الإيميل كهوية (انظر نموذج User لديك) :contentReference[oaicite:0]{index=0}
#         user.email = user.email.strip().lower()
#         user.is_active = False  # سيتم التفعيل عبر رابط التفعيل في register_view :contentReference[oaicite:1]{index=1}
#         user.set_password(self.cleaned_data["password1"])
#         if commit:
#             user.save()
#         return user
#
#
#
# class LoginForm(AuthenticationForm):
#     # AuthenticationForm يستخدم name=username؛ نعرضه كحقل بريد فقط
#     username = forms.EmailField(label="Email", widget=forms.EmailInput(attrs={"autocomplete": "email"}))
#
#
# class ProfileEditForm(forms.ModelForm):
#     class Meta:
#         model = User
#         fields = ("first_name", "last_name")