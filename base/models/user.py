# base/models/user.py
from __future__ import annotations
from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db.models.functions import Lower
from django.utils import timezone
from django.db.models import Q
from .mixins import TimeStampedMixin, ActivableMixin  # لديك هذه الميكسنز بالفعل
# الربط مع كيانات المشروع الجديد
# ملاحظة: نستخدم سلاسل لتفادي الدوران، لأن models تُحمَّل مبكرًا
# "base.Partner" و "base.Company" موجودان لديك
# - Partner: OneToOne (مثل contacts.Contact في المشروع القديم)
# - Company/companies: افتراضية + مسموح بها (Odoo-like)
# --------------------------------------------------------------------

class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra):
        if not email:
            raise ValueError("Users must have an email address")
        email = self.normalize_email(email).lower().strip()
        # AbstractUser يتطلب username كحقل، نولّده تلقائيًا إن لم يُمرّر
        extra.setdefault("username", email.split("@")[0])
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        return self._create_user(email, password, **extra)

    def get_by_natural_key(self, email):
        """
        يسمح بالبحث عن المستخدم باستخدام EMAIL كحقل دخول.
        Django يعتمد هذه الدالة عند createsuperuser/login.
        """
        return self.get(email__iexact=email.strip().lower())



class User(TimeStampedMixin, ActivableMixin, AbstractUser):
    """
    نسخة مطوّرة تجمع أفكار مشروع QMS + فروقات مشروعك الجديد:
    - تسجيل الدخول بالبريد (USERNAME_FIELD = email) مع بقاء username لأغراض Django
    - العلاقة مع Partner (OneToOne) كما في مشروعك الجديد
    - company (افتراضية) + companies (مسموح بها) كما لديك الآن
    - حقول إضافية من QMS: email_verified, email_verified_at, avatar, last_session_key
    - فهارس وقيود لأداء ونظافة البيانات
    """
    # هوية
    email = models.EmailField(unique=True, db_index=True)
    avatar = models.ImageField(upload_to="users/avatar/", blank=True, null=True)

    # حالة البريد
    email_verified = models.BooleanField(default=False)
    email_verified_at = models.DateTimeField(null=True, blank=True)

    # جلسات
    last_session_key = models.CharField(max_length=40, null=True, blank=True)

    # علاقات مشروعك
    partner = models.OneToOneField("base.Partner", on_delete=models.PROTECT,
                                   related_name="user", null=True, blank=True)
    company = models.ForeignKey("base.Company", on_delete=models.PROTECT,
                                related_name="users_default", null=True, blank=True)
    companies = models.ManyToManyField("base.Company", related_name="users", blank=True)

    # مدير
    objects = UserManager()

    # تسجيل الدخول بالبريد
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]  # AbstractUser يتطلب username كحقل موجود

    class Meta:
        db_table = "user"  # لا نغيّر الاسم لتجنّب ترحيلات ثقيلة (Odoo يستخدم res_users لكن المنطق نفسه)
        ordering = ("-date_joined",)

        # فهارس عملية للبحث والتقارير (PostgreSQL)
        indexes = [
            models.Index(Lower("email"), name="user_email_ci_idx"),  # بحث/فلترة بالبريد بحساسية حروف = صفر
            models.Index(fields=["company"], name="user_company_idx"),  # شائع في multi-company
            models.Index(fields=["is_active", "date_joined"], name="user_active_joined_idx"),
            models.Index(fields=["last_login"], name="user_last_login_idx"),
            models.Index(fields=["username"], name="user_username_idx"),  # إبقائه إن كان يُستخدم داخليًا
        ]

        # قيود تكامل (Odoo-like: login/email فريد وغير فارغ)
        constraints = [
            models.UniqueConstraint(Lower("email"), name="uniq_user_email_ci"),
            models.CheckConstraint(check=~Q(email=""), name="user_email_not_empty"),
        ]

        # صلاحيات مخصّصة يمكن التوسّع بها لاحقًا
        permissions = [
            ("share_user", "Can share user object"),
        ]

    # عرض مناسب
    @property
    def display_name(self) -> str:
        full = self.get_full_name().strip()
        if full:
            return full
        if self.partner and (self.partner.name or "").strip():
            return self.partner.name.strip()
        return self.email

    def __str__(self):
        return self.display_name

    def clean(self):
        super().clean()
        if self.email:
            self.email = self.__class__.objects.normalize_email(self.email).lower().strip()
        # تحقّق منطقي: الشركة الافتراضية يجب أن تكون ضمن المسموح بها (عند وجودها)
        # نخفف الشرط عند الإنشاء الأول لأن m2m لم تُحفظ بعد — signals ستضمن ذلك لاحقًا.
        if self.pk and self.company and not self.companies.filter(pk=self.company_id).exists():
            from django.core.exceptions import ValidationError
            raise ValidationError({"company": "Default company must be included in allowed companies."})

    def save(self, *args, **kwargs):
        # منع تعطيل آخر superuser فعّال
        if self.pk and not self.is_active and self.is_superuser:
            qs = type(self).objects.filter(is_superuser=True, is_active=True).exclude(pk=self.pk)
            if not qs.exists():
                from django.core.exceptions import ValidationError
                raise ValidationError("Cannot deactivate the last active superuser.")
        if self.email:
            self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    def anonymize_and_deactivate(self):
        """إخفاء بيانات المستخدم وتعطيله (بديل الحذف النهائي)."""
        ts = timezone.now().strftime("%Y%m%d%H%M%S")
        self.email = f"deleted+{self.pk}.{ts}@example.invalid"
        self.username = f"deleted_{self.pk}_{ts}"
        self.first_name = ""
        self.last_name = ""
        self.is_active = False
        self.active = False
        self.set_unusable_password()
        self.save(update_fields=["email", "username", "first_name", "last_name",
                                 "is_active", "active", "password"])


class UserSettings(TimeStampedMixin, models.Model):
    """
    تفضيلات المستخدم (مختصرة ومفيدة الآن؛ يمكن توسيعها لاحقًا):
    - الشركة الافتراضية في الواجهة
    - إعدادات واجهة عامة
    """
    user = models.OneToOneField("base.User", on_delete=models.CASCADE, related_name="settings")
    default_company = models.ForeignKey("base.Company", null=True, blank=True,
                                        on_delete=models.SET_NULL, related_name="defaulted_users")
    tz = models.CharField(max_length=64, default="Asia/Baghdad")
    lang = models.CharField(max_length=8, default="en_US")
    notification_type = models.CharField(
        max_length=16, choices=[("email", "Email"), ("inbox", "Inbox")], default="email"
    )
    signature = models.TextField(blank=True)
    theme = models.CharField(max_length=16, default="system")  # system/light/dark
    sidebar_state = models.CharField(max_length=16, default="expanded")
    redirect_after_login = models.CharField(max_length=128, blank=True)
    time_format_24h = models.BooleanField(default=True)
    date_format = models.CharField(max_length=32, default="YYYY-MM-DD")
    show_tips = models.BooleanField(default=True)

    class Meta:
        db_table = "users_settings"
        verbose_name = "User Settings"
        verbose_name_plural = "User Settings"

    def __str__(self):
        return f"Settings({self.user_id})"
