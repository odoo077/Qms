from __future__ import annotations
from django.core.validators import RegexValidator
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.db.models.functions import Lower
from django.utils import timezone
from django.db.models import Q
from django.core.exceptions import ValidationError
from base.company_context import get_company_id, get_allowed_company_ids
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.base_user import BaseUserManager
from django.apps import apps
from base.acl import ACLManager


# الربط مع كيانات المشروع الجديد
# ملاحظة: نستخدم سلاسل لتفادي الدوران، لأن models تُحمَّل مبكرًا
# "base.Partner" و "base.Company" موجودان لديك
# - Partner: OneToOne (مثل contacts.Contact في المشروع القديم)
# - Company/companies: افتراضية + مسموح بها (Odoo-like)
# --------------------------------------------------------------------


# --------------- Managers -------------

class CompanyScopeQuerySet(models.QuerySet):
    def _apply_company_scope(self):
        from base.company_context import get_allowed_company_ids
        active_ids = get_allowed_company_ids()
        if not active_ids:
            return self.none()
        # اسم حقل الـFK في Django يكون "company" (والعمود DB هو company_id)
        has_company_field = any(getattr(f, "name", None) == "company" for f in self.model._meta.get_fields())
        if has_company_field:
            return self.filter(company_id__in=active_ids)
        return self

    # تسهيلات شائعة
    def for_current_company(self):
        return self._apply_company_scope()

    def for_allowed_companies(self):
        allowed = get_allowed_company_ids()
        if not allowed:
            return self
        has_company_field = any(f.name == "company" for f in self.model._meta.get_fields())
        if has_company_field:
            return self.filter(company_id__in=allowed)
        return self


class CompanyScopeManager(models.Manager.from_queryset(CompanyScopeQuerySet)):
    use_in_migrations = True

    def get_queryset(self):
        qs = super().get_queryset()
        return qs._apply_company_scope()

    # للوصول بدون أي تقييد (حذر!)
    def all_companies(self):
        return super().get_queryset()

class ScopedACLManager(ACLManager):
    def get_queryset(self):
        qs = super().get_queryset()
        # طبّق سكوب الشركة هنا أيضًا
        if any(getattr(f, "name", None) == "company" for f in qs.model._meta.get_fields()):
            from base.company_context import get_allowed_company_ids
            active_ids = get_allowed_company_ids()
            qs = qs.filter(company_id__in=active_ids) if active_ids else qs.none()
        return qs

# ------------ Mixins --------------

# ---------- أساسية (وقت/تفعيل/عنوان) ----------
class TimeStampedMixin(models.Model):
    """ختم إنشـاء/تعديل مع فهارس."""
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        abstract = True


class ActivableMixin(models.Model):
    """حقل active مع فهرسة."""
    active = models.BooleanField(default=True, db_index=True)

    class Meta:
        abstract = True


class AddressMixin(models.Model):
    """حقول عنوان أساسية (نصية بسيطة كما في Odoo)."""
    street = models.CharField(max_length=255, blank=True)
    street2 = models.CharField(max_length=255, blank=True)
    zip = models.CharField(max_length=24, blank=True)
    city = models.CharField(max_length=128, blank=True)
    state = models.CharField(max_length=128, blank=True)
    country = models.CharField(max_length=128, blank=True)

    class Meta:
        abstract = True


# ---------- شركات وسكوب ----------
class CompanyOwnedMixin(models.Model):
    """
    أي موديل يرث منه سيحصل على:
    - حقل company (مع related_name عام)
    - مدير objects يقيّد الاستعلامات على الشركة النشطة
    - ضبط الشركة تلقائيًا من السياق عند الإنشاء إن لم تُحدد
    - فحص cross-company للعلاقات المذكورة في company_dependent_relations
      مع إمكان تجاهل علاقات معيّنة عبر COMPANY_SCOPE_IGNORE_RELATIONS
      وتجاهل تلقائي لأي علاقة تشير إلى base.Company (Odoo-like).
    """
    company = models.ForeignKey(
        "base.Company",
        on_delete=models.PROTECT,
        related_name="%(app_label)s_%(class)s_set",
        db_index=True,
    )

    # مدير مقيَّد افتراضيًا على الشركة الحالية
    objects = CompanyScopeManager()
    # مدير عام غير مقيَّد عند الحاجة
    all_objects = models.Manager()

    # أسماء الحقول العلائقية التي يجب أن تطابق self.company
    company_dependent_relations: tuple[str, ...] = ()

    class Meta:
        abstract = True
        indexes = [models.Index(fields=["company"])]

    def clean(self):
        super().clean()

        # قائمة استثناءات اختيارية يمكن تعريفها على الموديل الوريث (مثال: {"parent"})
        ignore_relations = set(getattr(self, "COMPANY_SCOPE_IGNORE_RELATIONS", ()))

        for rel_name in getattr(self, "company_dependent_relations", ()):
            # 0) تخطَّ إن كان الحقل ضمن الاستثناءات الصريحة
            if rel_name in ignore_relations:
                continue

            # 1) احصل على السجل المرتبط
            rel = getattr(self, rel_name, None)
            if not rel:
                continue

            # 2) تخطَّ الفحص لو العلاقة تشير إلى base.Company (Odoo-like: شركات خارج فحص company_id)
            try:
                rel_opts = rel._meta
                if rel_opts.app_label == "base" and rel_opts.model_name == "company":
                    continue
            except AttributeError:
                # ليس موديل Django (أو None) — لا نفحص
                continue

            # 3) استثناء Odoo-like: على Partner الشركة فقط، parent قد ينتمي لشركة مختلفة (الأم)
            #    partner.is_company=True AND relation is "parent" => لا نفحص
            try:
                if self._meta.model_name == "partner" and rel_name == "parent" and getattr(self, "is_company", False):
                    continue
            except AttributeError:
                pass

            # 4) لو أحد الطرفين بلا company_id لا معنى للفحص
            self_cid = getattr(self, "company_id", None)
            rel_cid = getattr(rel, "company_id", None)
            if not self_cid or not rel_cid:
                continue

            # 5) الفحص القياسي
            if rel_cid != self_cid:
                raise ValidationError({rel_name: "Related record belongs to a different company."})

    def save(self, *args, **kwargs):
        from base.company_context import get_company_id
        # في حال كانت الشركة فارغة: خذ current من السياق
        if hasattr(self, "company_id") and not self.company_id:
            current = get_company_id()
            if current:
                # إذا الحقل FK باسم "company"
                if hasattr(self, "company"):
                    self.company_id = current
        super().save(*args, **kwargs)


# ---------- تتبّع المستخدم (create_uid/write_uid على طريقة Odoo) ----------
class UserStampedMixin(models.Model):
    """حقول created_by / updated_by مرتبطة بمستخدم base.User."""
    created_by = models.ForeignKey(
        "base.User",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="%(class)s_created",
    )
    updated_by = models.ForeignKey(
        "base.User",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="%(class)s_updated",
    )

    class Meta:
        abstract = True

# ------------ Company models -----------

class Currency(models.Model):
    """Very light currency model so Company can point to one (Odoo-like)."""
    code = models.CharField(max_length=10, unique=True)  # e.g., IQD, USD
    name = models.CharField(max_length=64, blank=True)

    def __str__(self):
        return self.code


class Company(UserStampedMixin,TimeStampedMixin, ActivableMixin):
    """
    Django flavor of Odoo's res.company.
    - parent/children tree
    - identity details + reporting fields
    - default currency
    - accepted_users: users allowed to switch to this company (Odoo-like)
    """

    # Partner is the single source of truth for identity/address fields.
    # Keep only fields truly owned by Company (e.g., name). Colors/logo remain Company-owned.

    objects = ACLManager()

    SYNCED_WITH_PARTNER_FIELDS = ("name",)

    name = models.CharField(max_length=255, unique=True)
    parent = models.ForeignKey(
        "self", null=True, blank=True, related_name="children", on_delete=models.PROTECT
    )
    sequence = models.PositiveIntegerField(default=10, db_index=True)
    parent_path = models.CharField(max_length=255, blank=True, db_index=True)

    logo = models.ImageField(upload_to="company_logos/", blank=True, null=True)
    primary_color = models.CharField(max_length=16, blank=True)
    secondary_color = models.CharField(max_length=16, blank=True)

    currency = models.ForeignKey(Currency, on_delete=models.PROTECT, null=True, blank=True)

    # ✅ جديد: جهة الاتصال المقابلة للشركة
    partner = models.OneToOneField(
        "base.Partner", null=True, blank=True,
        on_delete=models.PROTECT, related_name="company_profile"
    )

    # ---- Read-only identity proxies to Partner (single source of truth) ----
    @property
    def email(self):
        return self.partner.email if self.partner_id else ""

    @property
    def phone(self):
        return self.partner.phone if self.partner_id else ""

    @property
    def website(self):
        return self.partner.website if self.partner_id else ""

    @property
    def vat(self):
        return self.partner.vat if self.partner_id else ""

    @property
    def company_registry(self):
        return self.partner.company_registry if self.partner_id else ""

    # Address proxies:
    @property
    def street(self):
        return self.partner.street if self.partner_id else ""

    @property
    def street2(self):
        return self.partner.street2 if self.partner_id else ""

    @property
    def city(self):
        return self.partner.city if self.partner_id else ""

    @property
    def state(self):
        return self.partner.state if self.partner_id else ""

    @property
    def zip(self):
        return self.partner.zip if self.partner_id else ""

    @property
    def country(self):
        return self.partner.country if self.partner_id else ""

    def clean(self):
        """
        سلامة البيانات للشجرة ومطابقة بطاقة الشريك (Odoo-like):

        1) منع كون الشركة أبًا لنفسها.
        2) منع الحلقات (الدورات) في الشجرة (parent ⟶ ... ⟶ self).
        3) إن كانت بطاقة الشريك محددة، يجب أن تكون partner.is_company = True.
        4) مواءمة الشجرة: إن كان لكلٍ من self.parent و self.partner و parent.partner قيم،
           فيُفترض أن يكون partner.parent = parent.partner (تناسق شجرة الشركات وجهات اتصالها).
           (لا نُعدِّل هنا، نتحقق فقط ونُبلغ بخطأ إدخال إن كان هناك عدم اتساق واضح.)
        5) تثبيت التطابق: إن كانت هذه الشركة مربوطة ببطاقة Partner،
           يجب أن يشير partner.company إلى هذه الشركة نفسها.
        """

        # 1) منع ذات-الأب
        if self.pk and self.parent_id and self.parent_id == self.pk:
            raise ValidationError({"parent": "Parent company cannot be self."})

        # 2) منع الحلقات
        node = self.parent
        seen = set()
        while node:
            if self.pk and node.pk == self.pk:
                raise ValidationError({"parent": "Cyclic hierarchy is not allowed."})
            if node.pk in seen:
                # حماية إضافية إن حدث تكرار غير متوقع
                raise ValidationError({"parent": "Cyclic hierarchy is not allowed."})
            seen.add(node.pk)
            node = node.parent

        # 3) بطاقة الشريك يجب أن تمثل شركة
        if self.partner_id and getattr(self.partner, "is_company", None) is not True:
            raise ValidationError({"partner": "Linked partner must be of type 'company'."})

        # 4) مواءمة الشجرة بين Company و Partner (تحقق منطقي فقط)
        if self.parent_id and self.partner_id:
            parent_partner = getattr(self.parent, "partner", None)
            if parent_partner and self.partner.parent_id and self.partner.parent_id != parent_partner.id:
                raise ValidationError({
                    "partner": "Partner's parent must match parent company's partner."
                })

        # 5) تثبيت التطابق بين Partner.company وهذه الشركة
        if self.partner_id and getattr(self.partner, "company_id", None) and self.partner.company_id != self.id:
            raise ValidationError({"partner": "Partner.company must match this Company."})

    def save(self, *args, **kwargs):
        """
        Company.save (Odoo-like):
          - لا ننشئ Partner هنا (توليده منوط بالـ signal بعد اكتمال المعاملة لضمان الاتساق).
          - نحسب parent_path دومًا بعد توفّر pk وبعد أي تعديل على parent.
        """
        # 1) احفظ أولاً للحصول على PK
        super().save(*args, **kwargs)

        # 2) حساب المسار المادّي بعد وجود pk وربما بعد ضبط parent
        new_path = f"{self.pk}/"
        if self.parent and self.parent.parent_path:
            new_path = f"{self.parent.parent_path}{self.pk}/"
        elif self.parent:
            new_path = f"{self.parent.pk}/{self.pk}/"

        if self.parent_path != new_path:
            self.parent_path = new_path
            super().save(update_fields=["parent_path"])


    class Meta:
        db_table = "company"
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["active"]),
        ]

    def __str__(self):
        return self.name


# ------------ User models --------------


class UserManager(BaseUserManager):
    """
    مدير مستخدمين بمنطق Odoo-like:
      - يعتمد البريد كحقل دخول (natural key).
      - يملأ الشركة الافتراضية تلقائيًا للمستخدمين الجدد إن لم تُمرّر.
      - ينشئ Main Company تلقائيًا عند إنشاء أول superuser (إن لم توجد).
    """
    use_in_migrations = True

    # ------------------------------------------------------
    # لبّ الإنشاء الداخلي
    # ------------------------------------------------------
    def _create_user(self, email, password, **extra):
        """
        إنشاء مستخدم فعلي:
          - تطبيع البريد (lower/strip).
          - توليد username تلقائيًا إن لم يُمرّر.
          - حفظ كلمة المرور بشكل آمن.
        """
        if not email:
            raise ValueError("Users must have an email address")

        email = self.normalize_email(email).lower().strip()
        # AbstractUser يتطلب username كحقل، نولّده تلقائيًا إن لم يُمرّر
        extra.setdefault("username", (email.split("@")[0] if "@" in email else email))

        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    # ------------------------------------------------------
    # مستخدم عادي (Signup / Admin) — Odoo-like
    # ------------------------------------------------------
    def create_user(self, email, password=None, **extra):
        """
        مستخدم عادي:
          - is_staff=False, is_superuser=False افتراضيًا.
          - إن لم تُمرّر company، نستخدم Main Company (أول شركة موجودة).
          - إن لم توجد شركة أصلًا (نادرًا)، نطلب إنشاء شركة أولًا.
        """
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)

        # لو لم تُحدَّد الشركة صراحة، اختر أول شركة (Main Company)
        if "company" not in extra or extra.get("company") is None:
            Company = apps.get_model("base", "Company")
            main_company = Company.objects.order_by("id").first()
            if main_company is None:
                # يحصل فقط إن لم تُنشأ شركة بعد (قبل migrate أو قبل bootstrap أول شركة)
                raise ValueError("No company found. Please create a company first.")
            extra["company"] = main_company

        return self._create_user(email, password, **extra)

    # ------------------------------------------------------
    # سوبر يوزر — Bootstrap لـ Main Company إن لزم
    # ------------------------------------------------------
    def create_superuser(self, email, password=None, **extra):
        """
        عند إنشاء superuser لأول مرة:
          - إذا لم توجد شركة بعد، تُنشأ "Main Company" تلقائيًا (مثل Odoo).
          - يربط المستخدم بها تلقائيًا.
        """
        Company = apps.get_model("base", "Company")
        Partner = apps.get_model("base", "Partner")

        # تأكد من وجود شركة واحدة على الأقل
        main_company = Company.objects.order_by("id").first()
        if not main_company:
            # أنشئ الشريك والشركة مثل bootstrap_main_company
            partner = Partner.objects.create(
                name="Main Company",
                is_company=True,
                company_type="company",
                type="contact",
            )
            main_company = Company.objects.create(name="Main Company", partner=partner)
            print("✅ Auto-created Main Company for first superuser.")

        # اضبط حقول السوبر
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("company", main_company)

        return self._create_user(email, password, **extra)

    # ------------------------------------------------------
    # الدخول بالبريد (natural key)
    # ------------------------------------------------------
    def get_by_natural_key(self, email):
        """
        يسمح بالبحث عن المستخدم باستخدام EMAIL كحقل دخول.
        Django يعتمد هذه الدالة عند createsuperuser/login.
        """
        return self.get(email__iexact=(email or "").strip().lower())


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
    # استخدمنا PROTECT بدل SET_NULL لأن حذف الشركة يجب أن يمنع حذفها إذا كانت مرتبطة بمستخدم (مثل Odoo بالضبط).
    company = models.ForeignKey(
        "Company",
        on_delete=models.PROTECT,
        null=False,
        blank=False,
        related_name="user_default_company",
        verbose_name=_("Company"),
    )

    companies = models.ManyToManyField(
        "base.Company",
        related_name="users",
        blank=True,
    )

    # مدير
    objects = UserManager()
    acl_objects = ACLManager()
    scoped_objects = ScopedACLManager()

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
        """
        سلوك Odoo-like:
          - فرض وجود شركة افتراضية للمستخدم (company) وعدم تركها فارغة.
          - إن لم تُحدَّد، نملؤها تلقائيًا بأول شركة موجودة (الشركة الرئيسية).
          - تنسيق البريد الإلكتروني إلى lower + strip.
          - لا نمنع الحفظ إذا لم تكن الشركة الافتراضية ضمن المسموح بها؛
            لأن تحديث الـ m2m (allowed companies) يتم بعد الحفظ وتتكفّل به الإشارات.
        """
        super().clean()

        # تنسيق البريد الإلكتروني
        if self.email:
            self.email = self.__class__.objects.normalize_email(self.email).lower().strip()

        # إلزام وجود شركة افتراضية: إن لم تُحدد نختار أول شركة (كما يفعل Odoo)
        if not self.company_id:
            from base.models import Company
            main_company = Company.objects.order_by("id").first()
            if main_company is not None:
                self.company = main_company
            else:
                # لا توجد شركات في النظام بعد — اطلب من المستخدم إنشاء شركة أولًا
                from django.core.exceptions import ValidationError
                raise ValidationError({"company": "A default company is required. Please create a company first."})

        # ملاحظة مهمة:
        # لا نرمي ValidationError إذا لم تكن الشركة الافتراضية ضمن المسموح بها هنا،
        # لأن m2m تُحفظ بعد الحفظ. إشارات m2m (ensure_default_in_allowed)
        # ستضمن إضافة الشركة الافتراضية تلقائيًا إلى allowed companies.
        # إذا أردت تحذيرًا فقط (بدون منع الحفظ)، يمكن لاحقًا إضافته في الفورم/الأدمن.

    def save(self, *args, **kwargs):
        # 1) منع تعطيل آخر superuser فعّال (كما في كودك الحالي)
        if self.pk and not self.is_active and self.is_superuser:
            qs = type(self).objects.filter(is_superuser=True, is_active=True).exclude(pk=self.pk)
            if not qs.exists():
                from django.core.exceptions import ValidationError
                raise ValidationError("Cannot deactivate the last active superuser.")

        # 2) تطبيع البريد قبل الحفظ
        if self.email:
            self.email = self.email.strip().lower()

        # 3) احفظ المستخدم أولاً
        super().save(*args, **kwargs)

        # 4) Odoo-like: تأكد أن الشركة الافتراضية ضمن المسموح بها
        if getattr(self, "company_id", None) and not self.companies.filter(pk=self.company_id).exists():
            self.companies.add(self.company_id)

        # 5) Odoo-like: عكس الافتراضي إلى UserSettings (إن وجدت)
        settings = None
        try:
            settings = self.settings  # OneToOne related_name="settings"
        except Exception:
            settings = None
        if settings and getattr(settings, "default_company_id", None) != self.company_id:
            settings.default_company_id = self.company_id
            settings.save(update_fields=["default_company"])

        # 6) NEW: مزامنة Partner الشخص مع الشركة الافتراضية
        #    - partner.company = user.company
        #    - partner.parent  = user.company.partner (لو موجود)
        if getattr(self, "partner_id", None) and getattr(self, "company_id", None):
            p = self.partner
            desired_company_id = self.company_id
            desired_parent_partner_id = getattr(self.company, "partner_id", None)

            updates = []
            if getattr(p, "company_id", None) != desired_company_id:
                p.company_id = desired_company_id
                updates.append("company")
            # للشخص فقط (is_company=False): اربط parent ببطاقة شركة المستخدم
            if getattr(p, "is_company", False) is not True:
                if getattr(p, "parent_id", None) != desired_parent_partner_id:
                    p.parent_id = desired_parent_partner_id
                    updates.append("parent")

            if updates:
                p.save(update_fields=updates)

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

    objects = ACLManager()

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

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # اجعل الافتراضي الحاكم هو user.company (Odoo-like)
        if getattr(self, "default_company_id", None) and getattr(self, "user_id", None):
            user = self.user
            # لو اختلف، حدّث user.company
            if user.company_id != self.default_company_id:
                user.company_id = self.default_company_id
                user.save(update_fields=["company"])
            # تأكد أن الافتراضي ضمن المسموح بها
            if not user.companies.filter(pk=self.default_company_id).exists():
                user.companies.add(self.default_company_id)

    def __str__(self):
        return f"Settings({self.user_id})"


# ------ Partner models --------

class PartnerCategory(models.Model):
    """Partner tags (res.partner.category)."""
    name = models.CharField(max_length=128)
    color = models.PositiveSmallIntegerField(default=0)
    parent = models.ForeignKey("self", null=True, blank=True, related_name="children", on_delete=models.CASCADE)
    complete_name = models.CharField(max_length=256, blank=True, db_index=True)
    parent_path = models.CharField(max_length=255, blank=True, db_index=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # materialized path: "1/5/9/"
        new_path = f"{self.pk}/"
        if self.parent and self.parent.parent_path:
            new_path = f"{self.parent.parent_path}{self.pk}/"
        elif self.parent:
            new_path = f"{self.parent.pk}/{self.pk}/"
        # حدّث المسار والاسم الكامل مرة ثانية فقط عند الحاجة
        new_complete = self.name if not self.parent else f"{self.parent.complete_name} / {self.name}"
        updates = []
        if self.parent_path != new_path:
            self.parent_path = new_path
            updates.append("parent_path")
        if self.complete_name != new_complete:
            self.complete_name = new_complete
            updates.append("complete_name")
        if updates:
            super(PartnerCategory, self.__class__).save(self, update_fields=updates)

    class Meta:
        db_table = "partner_category"
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["complete_name"]),
            models.Index(fields=["parent_path"]),
        ]

    def __str__(self):
        return self.name


class Partner(CompanyOwnedMixin, UserStampedMixin, TimeStampedMixin, ActivableMixin, AddressMixin):
    """
    Django flavor of Odoo's res.partner.
    - companies & persons share same table
    - company/person switch via company_type
    - parent link to represent a company's contacts
    - commercial_partner (computed-like property)
    """

    objects = ScopedACLManager()

    TYPE_CHOICES = [
        ("contact", "Contact"),
        ("invoice", "Invoice"),
        ("delivery", "Delivery"),
        ("other", "Other"),
    ]
    COMPANY_TYPE_CHOICES = [
        ("person", "Person"),
        ("company", "Company"),
    ]

    # Identity
    name = models.CharField(max_length=255, db_index=True, blank=True)
    display_name = models.CharField(max_length=512, blank=True, db_index=True)
    is_company = models.BooleanField(default=False)
    company_type = models.CharField(max_length=10, choices=COMPANY_TYPE_CHOICES, default="person")
    type = models.CharField(max_length=10, choices=TYPE_CHOICES, default="contact")

    # Hierarchy
    parent = models.ForeignKey(
        "self", null=True, blank=True, related_name="children", on_delete=models.SET_NULL
    )
    # نسخة مسطّحة من parent.company لتجنّب أي JOIN في القيود/الاستعلامات
    parent_company = models.ForeignKey(
        "base.Company", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="partner_children_all", editable=False, db_index=True,
    )

    # Company ownership (company-dependent)
    company = models.ForeignKey(
        "base.Company", null=True, blank=True, on_delete=models.SET_NULL, related_name="partners"
    )

    # Contact info
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=64, blank=True)
    mobile = models.CharField(max_length=64, blank=True)  # NEW: Odoo-like
    website = models.URLField(blank=True)

    # Fiscal identity
    vat = models.CharField(
        "Tax ID", max_length=64, blank=True,
        validators=[RegexValidator(r"^[^<>]*$", "Invalid characters in VAT")]
    )
    company_registry = models.CharField("Company ID", max_length=64, blank=True)

    # Categorization / relations
    categories = models.ManyToManyField(PartnerCategory, related_name="partners", blank=True)
    # هذه علاقة “مسوّق\مندوب” شائعة في أودو، لكنها ليست ضرورية الآن لأن مشروعك HR فقط—يمكن إبقاؤها بدون استعمال
    salesperson = models.ForeignKey(
        "base.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="customer_set"
    )
    employee = models.BooleanField(default=False)

    # ملاحظة مهمة:
    # في Odoo بطاقة الشركة (Partner للشركة) يكون Parent = بطاقة شركة الأب،
    # وغالبًا تكون لكل منهما شركة مختلفة. لذلك لا نفرض تطابق الشركة لعلاقة parent.
    company_dependent_relations: tuple[str, ...] = ()
    COMPANY_SCOPE_IGNORE_RELATIONS = {"parent"}

    class Meta:
        db_table = "partner"

        # ترتيب عرض افتراضي غير حساس لحالة الأحرف (للقوائم الكبيرة)
        ordering = [Lower("name")]

        # فهارس عملية (PostgreSQL-friendly)
        indexes = [
            models.Index(Lower("name"), name="partner_name_ci_idx"),
            models.Index(fields=["display_name"], name="partner_disp_idx"),
            models.Index(fields=["company_type"], name="partner_ctype_idx"),
            models.Index(fields=["type"], name="partner_type_idx"),
            models.Index(fields=["active"], name="partner_active_idx"),
            models.Index(fields=["parent"], name="partner_parent_idx"),
            models.Index(fields=["company"], name="partner_company_idx"),
            models.Index(fields=["parent_company", "company_type", "type"], name="partner_flat_parent_mix_idx"),
            models.Index(fields=["company", "is_company", "name"], name="partner_comp_iscomp_name_idx"),
        ]

        # قيود سلامة/تفرد (بدون JOIN قدر الإمكان)
        constraints = [

            # منع ذات-الأب على مستوى DB كذلك (حماية مزدوجة مع clean())
            models.CheckConstraint(
                name="partner_no_self_parent",
                check=~models.Q(parent=models.F("id")),
            ),

            # VAT فريد داخل نفس الشركة عند تحديده
            models.UniqueConstraint(
                fields=["company", "vat"],
                name="partner_unique_vat_per_company",
                condition=models.Q(vat__gt=""),
                violation_error_message="VAT must be unique per company when set.",
            ),

            # Company Registry فريد داخل نفس الشركة عند تحديده
            models.UniqueConstraint(
                fields=["company", "company_registry"],
                name="partner_unique_registry_per_company",
                condition=models.Q(company_registry__gt=""),
                violation_error_message="Company Registry must be unique per company when set.",
            ),

            # company_type مطابق لـ is_company (Odoo-like)
            models.CheckConstraint(
                name="partner_company_type_matches_flag",
                check=(
                    (models.Q(is_company=True, company_type="company")) |
                    (models.Q(is_company=False, company_type="person"))
                ),
            ),

            # الشخص لا يكون type != contact (يجنب أخطاء تعيين عنوان بدلاً من جهة اتصال شخص)
            models.CheckConstraint(
                name="partner_person_must_be_contact_type",
                check=(
                    models.Q(is_company=True) |
                    models.Q(is_company=False, type="contact")
                ),
            ),
        ]

    # -------- Validation & Persistence --------

    def clean(self):
        """
        اتساق البيانات ونطاق الشركات (Odoo-like):

        1) حفظ مرآة 'parent_company' لاستخدامها في الفلاتر/الفهارس بدون JOIN.
        2) توحيد company_type تلقائيًا من is_company.
        3) منع الحالة الشاذة: السجل لا يمكن أن يكون أبًا لنفسه.
        4) تفويض تحققات الميكسنز (ومنها توافق الشركة لعلاقة 'parent' لأنّها company-dependent).
        """

        # 1) مرآة شركة الأب لتسريع الاستعلامات/القيود
        self.parent_company = (
            self.parent.company if (self.parent_id and self.parent and self.parent.company_id) else None
        )

        # 2) توحيد نوع الشريك
        self.company_type = "company" if self.is_company else "person"

        # 3) منع ذات-الأب
        if self.parent_id and self.pk and self.parent_id == self.pk:
            raise ValidationError({"parent": "Parent cannot be self."})

        # 4) تحققات الميكسنز
        super().clean()

    def compute_display_name(self) -> str:
        if self.parent_id and not self.is_company:
            parent_name = (self.parent.name or "").strip()
            this = (self.name or dict(self.TYPE_CHOICES).get(self.type, "")).strip()
            return f"{parent_name}, {this}".strip(", ")
        return (self.name or "").strip()

    def save(self, *args, **kwargs):
        # صيانة الحقل المسطّح
        self.parent_company = (
            self.parent.company if (self.parent_id and self.parent and self.parent.company_id) else None
        )

        # توريث salesperson من الأب إذا كان شخصًا ولم يُحدد
        if not self.is_company and self.parent_id and not self.salesperson_id:
            self.salesperson_id = getattr(self.parent, "salesperson_id", None)

        # تحقّق + احتساب display_name
        self.clean()
        self.display_name = self.compute_display_name()

        # ✅ مهم: لو استُخدم update_fields في أي حفظ (مثلاً من sync أو signals)،
        # ضمن display_name حتى يُحفظ فعليًا في قاعدة البيانات.
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            if isinstance(update_fields, (list, tuple, set)):
                uf = set(update_fields)
            else:
                uf = {update_fields}
            uf.add("display_name")
            kwargs["update_fields"] = list(uf)

        super().save(*args, **kwargs)

    def __str__(self):
        return self.display_name or self.name or ""

    # -------- Odoo-like helpers --------
    @property
    def commercial_partner(self) -> "Partner":
        node = self
        while node and not node.is_company and node.parent:
            node = node.parent
        return node or self
