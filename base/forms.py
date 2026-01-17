from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, ReadOnlyPasswordHashField
from django.core.exceptions import ValidationError
from .models import Partner
from base.models import Company

User = get_user_model()

# ----- auth & profile forms -----------

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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        base_class = "input-auth"

        self.fields["email"].widget.attrs.update({
            "class": base_class,
            "placeholder": "you@example.com",
            "autocomplete": "email",
        })
        self.fields["username"].widget.attrs.update({
            "class": base_class,
            "placeholder": "your.username",
            "autocomplete": "username",
        })
        self.fields["first_name"].widget.attrs.update({
            "class": base_class,
            "placeholder": "John",
        })
        self.fields["last_name"].widget.attrs.update({
            "class": base_class,
            "placeholder": "Doe",
        })

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
    # نعرض حقل الـ username كبريد إلكتروني
    username = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={"autocomplete": "email"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        base_class = "input-auth"

        self.fields["username"].widget.attrs.update({
            "class": base_class,
            "placeholder": "you@example.com",
        })
        self.fields["password"].widget.attrs.update({
            "class": base_class + " pr-12",
            "placeholder": "••••••••",
            "autocomplete": "current-password",
        })


class UserCreateForm(forms.ModelForm):
    """
    User creation form (FINAL – Correct & Safe)

    Principles:
    - username is a SYSTEM field (not user-facing)
    - username is generated from email
    - username is ALWAYS set on the model instance
    - uniqueness is guaranteed at form level
    """

    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput,
        strip=False,
    )
    password2 = forms.CharField(
        label="Confirm password",
        widget=forms.PasswordInput,
        strip=False,
    )

    class Meta:
        model = User
        fields = (
            "email",
            "first_name",
            "last_name",
            "company",
            "companies",
        )

    # --------------------------------------------------
    # Email validation
    # --------------------------------------------------
    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()

        if not email:
            raise forms.ValidationError("Email is required.")

        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("User with this email already exists.")

        return email

    # --------------------------------------------------
    # Global validation
    # --------------------------------------------------
    def clean(self):
        cleaned = super().clean()

        # ---- Password validation ----
        p1 = cleaned.get("password1")
        p2 = cleaned.get("password2")

        if not p1 or not p2:
            raise forms.ValidationError("Password and confirmation are required.")

        if p1 != p2:
            raise forms.ValidationError("Passwords do not match.")

        # ---- Username generation (store for save) ----
        email = cleaned.get("email")
        if email:
            base = email.split("@")[0]
            username = base
            counter = 1

            while User.objects.filter(username=username).exists():
                username = f"{base}{counter}"
                counter += 1

            # نخزنها لاستخدامها في save()
            self._generated_username = username

        return cleaned

    # --------------------------------------------------
    # Persistence
    # --------------------------------------------------
    def save(self, commit=True):
        user = super().save(commit=False)

        # ✅ تعيين username صراحة (هذا هو الفرق الحاسم)
        user.username = getattr(self, "_generated_username", None)

        if not user.username:
            raise ValueError("Username was not generated.")

        # Set hashed password
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
        fields = ("first_name", "last_name", "avatar")

# ----- company forms -----------

class CompanySwitchForm(forms.Form):
    """
    نموذج تبديل الشركات (Multi-company switch) على نمط Odoo.

    الوظيفة:
    - يسمح باختيار شركة أو أكثر للعمل ضمنها.
    - الشركات المعروضة تقتصر على:
        * جميع الشركات إن كان المستخدم superuser
        * أو الشركات المرتبطة بالمستخدم (user.companies)
    - يملأ القيم الافتراضية (initial) بالشركات النشطة حاليًا إن وُجدت.
    """

    def __init__(self, *args, user=None, current_ids=None, **kwargs):
        super().__init__(*args, **kwargs)

        # --------------------------------------------------
        # تحديد queryset الشركات المسموح بها
        # --------------------------------------------------
        if user and getattr(user, "is_superuser", False):
            # superuser: يرى جميع الشركات (متوافق مع context processor و CompanySwitchView)
            qs = Company.objects.all()
        elif user:
            # مستخدم عادي: فقط الشركات المرتبطة به
            qs = user.companies.all()
        else:
            qs = Company.objects.none()

        # --------------------------------------------------
        # حقل اختيار الشركات
        # --------------------------------------------------
        self.fields["companies"] = forms.ModelMultipleChoiceField(
            queryset=qs,
            required=True,
            label="Companies",
            help_text="Select one or more companies to work under.",
            widget=forms.SelectMultiple(
                attrs={
                    "class": "select select-bordered w-full",
                    "size": 6,
                }
            ),
        )

        # --------------------------------------------------
        # تهيئة القيم الافتراضية (الشركات النشطة حاليًا)
        # --------------------------------------------------
        if current_ids:
            self.initial["companies"] = qs.filter(id__in=current_ids)


# ----- partner forms -----------

class PartnerForm(forms.ModelForm):
    """
    Partner form (FINAL – Best Practice):

    Principles:
    - Company is the SINGLE source of truth for hierarchy.
    - Partner MUST NOT control or affect Company.parent.
    - This form edits IDENTITY & CONTACT data ONLY.
    - No hierarchy, no company binding, no structural logic here.
    """

    class Meta:
        model = Partner
        fields = (
            # Identity & Contact
            "name",
            "email",
            "phone",
            "website",
            "vat",

            # Address
            "street",
            "street2",
            "zip",
            "city",
            "state",
            "country",

            # Status
            "active",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["active"].label = "Active"
        self.fields["active"].required = False

        # 🔒 Safety: ensure hierarchy-related fields are NEVER exposed
        for forbidden in ("parent", "company", "is_company"):
            self.fields.pop(forbidden, None)

    def clean(self):
        """
        Safety net:
        - Allow presence of structural fields in POST
        - Forbid changing their VALUES
        """
        cleaned = super().clean()

        if not self.instance.pk:
            return cleaned

        # قيم الأصل من قاعدة البيانات
        original = Partner.objects.get(pk=self.instance.pk)

        # 🔒 لا نسمح بتغيير القيم، لا مجرد وجودها
        if "company" in cleaned and cleaned["company"] != original.company:
            raise forms.ValidationError(
                "Company relation is managed exclusively from Company."
            )

        if "parent" in cleaned and cleaned["parent"] != original.parent:
            raise forms.ValidationError(
                "Hierarchy is managed exclusively from Company."
            )

        if "is_company" in cleaned and cleaned["is_company"] != original.is_company:
            raise forms.ValidationError(
                "Partner type cannot be changed."
            )

        return cleaned


class PartnerFilterForm(forms.Form):
    """
    Partner Filter Form (Directory-grade)

    Used by PartnerListView only.
    No save(), no side-effects.
    """

    q = forms.CharField(
        required=False,
        label="Search",
        widget=forms.TextInput(attrs={
            "placeholder": "Search name, email, phone…"
        })
    )

    company = forms.ModelChoiceField(
        queryset=Company.objects.none(),
        required=False,
        empty_label="All allowed companies",
        label="Company"
    )

    company_type = forms.ChoiceField(
        choices=[("", "All")] + Partner.COMPANY_TYPE_CHOICES,
        required=False,
        label="Company Type"
    )

    type = forms.ChoiceField(
        choices=[("", "All")] + Partner.TYPE_CHOICES,
        required=False,
        label="Contact Type"
    )

    active = forms.ChoiceField(
        choices=[
            ("", "All"),
            ("1", "Active"),
            ("0", "Inactive"),
        ],
        required=False,
        label="Status"
    )

    employee = forms.ChoiceField(
        choices=[
            ("", "All"),
            ("1", "Employee"),
            ("0", "Not employee"),
        ],
        required=False,
        label="Employee"
    )

    order = forms.ChoiceField(
        choices=[
            ("name", "Name (A–Z)"),
            ("latest", "Latest"),
            ("company", "Company"),
        ],
        required=False,
        initial="name",
        label="Order by"
    )

    # -----------------------------
    # Dynamic queryset injection
    # -----------------------------
    def __init__(self, *args, **kwargs):
        allowed_companies = kwargs.pop("allowed_companies", None)
        super().__init__(*args, **kwargs)

        if allowed_companies is not None:
            self.fields["company"].queryset = allowed_companies


# ----- user forms -----------

class UserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = (
            "email",
            "first_name",
            "last_name",

            # Status
            "is_active",

            # Company scope
            "company",
            "companies",
        )


class UserFilterForm(forms.Form):
    """
    Enterprise-grade User search & filter form (Odoo-like)

    Purpose:
    - Used ONLY for listing & filtering users
    - No save()
    - Pure query intent
    """

    # -------------------------------------------------
    # Search
    # -------------------------------------------------
    q = forms.CharField(
        required=False,
        label="Search",
        widget=forms.TextInput(attrs={
            "placeholder": "Search by email, name, partner…",
            "class": "input input-bordered input-sm w-full",
        }),
    )

    # -------------------------------------------------
    # Company filters
    # -------------------------------------------------
    company = forms.ModelChoiceField(
        queryset=Company.objects.none(),  # injected from view
        required=False,
        label="Company",
        widget=forms.Select(attrs={
            "class": "select select-bordered select-sm w-full",
        }),
    )

    # -------------------------------------------------
    # Status
    # -------------------------------------------------
    is_active = forms.NullBooleanField(
        required=False,
        label="Status",
        widget=forms.Select(choices=[
            ("", "All"),
            ("true", "Active"),
            ("false", "Inactive"),
        ], attrs={
            "class": "select select-bordered select-sm w-full",
        }),
    )

    # -------------------------------------------------
    # Email verification
    # -------------------------------------------------
    email_verified = forms.NullBooleanField(
        required=False,
        label="Email verified",
        widget=forms.Select(choices=[
            ("", "All"),
            ("true", "Verified"),
            ("false", "Not verified"),
        ], attrs={
            "class": "select select-bordered select-sm w-full",
        }),
    )

    # -------------------------------------------------
    # Superuser / Staff
    # -------------------------------------------------
    is_staff = forms.NullBooleanField(
        required=False,
        label="Staff",
        widget=forms.Select(choices=[
            ("", "All"),
            ("true", "Staff only"),
            ("false", "Non-staff"),
        ], attrs={
            "class": "select select-bordered select-sm w-full",
        }),
    )

    is_superuser = forms.NullBooleanField(
        required=False,
        label="Superuser",
        widget=forms.Select(choices=[
            ("", "All"),
            ("true", "Superusers"),
            ("false", "Non-superusers"),
        ], attrs={
            "class": "select select-bordered select-sm w-full",
        }),
    )

    # -------------------------------------------------
    # Ordering
    # -------------------------------------------------
    order = forms.ChoiceField(
        required=False,
        choices=[
            ("email", "Email (A–Z)"),
            ("name", "Name (A–Z)"),
            ("company", "Company"),
            ("latest", "Latest"),
        ],
        widget=forms.Select(attrs={
            "class": "select select-bordered select-sm w-full",
        }),
    )

    # -------------------------------------------------
    # Dynamic injection (company scope)
    # -------------------------------------------------
    def set_company_queryset(self, qs):
        """
        Inject allowed companies from view (company scope aware).
        """
        self.fields["company"].queryset = qs.order_by("name")

# ----- Company forms -----------

# ----- Company forms -----------

class CompanyForm(forms.ModelForm):
    """
    Company form:
    - Editable fields:
        - name
        - parent   ✅ (مصدر الحقيقة)
        - active
    - Partner is managed automatically via signals
    """

    class Meta:
        model = Company
        fields = ("name", "parent", "active")
        widgets = {
            "active": forms.CheckboxInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # parent اختياري
        self.fields["parent"].required = False

    def clean_name(self):
        name = self.cleaned_data.get("name", "")
        name = name.strip()

        if not name:
            raise forms.ValidationError("Company name cannot be empty.")

        qs = Company.objects.filter(name__iexact=name)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise forms.ValidationError("A company with this name already exists.")

        return name
