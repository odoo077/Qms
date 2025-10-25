"""
Django settings for Qms project.
"""

# استخدام مكتبة django-environ لقراءة القيم من .env
import environ
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent



# تعريف env مع قيم افتراضية
# القيم الحساسة مثل SECRET_KEY, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD, DB_PASSWORD → لا علاقة لها بـ default.
env = environ.Env(
    DEBUG=(bool, False),
    EMAIL_PORT=(int, 465),
    EMAIL_USE_SSL=(bool, True),
    EMAIL_USE_TLS=(bool, False),
    EMAIL_TIMEOUT=(int, 20),
    DB_PORT=(int, 5432),
)

# تحميل ملف .env
environ.Env.read_env(os.path.join(BASE_DIR, ".env"))

# ========== Debug ==========
DEBUG = env("DEBUG")
SECRET_KEY = env("SECRET_KEY")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["127.0.0.1", "localhost"])

# ========== Database ==========
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("DB_NAME"),
        "USER": env("DB_USER"),
        "PASSWORD": env("DB_PASSWORD"),
        "HOST": env("DB_HOST", default="localhost"),
        "PORT": env("DB_PORT"),
    }
}

# ========== Email ==========

SITE_URL = env("SITE_URL", default="http://127.0.0.1:8000")

EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT = env("EMAIL_PORT")
EMAIL_USE_SSL = env("EMAIL_USE_SSL")
EMAIL_USE_TLS = env("EMAIL_USE_TLS")
EMAIL_HOST_USER = env("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default=EMAIL_HOST_USER)
EMAIL_TIMEOUT = env("EMAIL_TIMEOUT")


# -------------------------------------------------
# Applications
#  ملاحظة مهمة: ضع base قبل أي تطبيقات أخرى لأنه يعرّف AUTH_USER_MODEL
# -------------------------------------------------
INSTALLED_APPS = [
    # Django
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Third-party
    "guardian",                 # Object-level permissions (مثل Odoo access rules)
    "tailwind",
    "theme",

    # "django_browser_reload"  # سيُضاف تلقائياً بالأسفل عندما DEBUG=True

    # Project apps (Odoo-like)
    'base.apps.BaseConfig',         # ← يحتوي User/Company/Partner… (يجب أن يأتي أولاً)
    "employees",
    "hr.apps.HrConfig",
    "skills",
    "assets",
    "performance",
    "payroll",
    'xfields',
    "widget_tweaks",
]

# -------------------------------------------------
# Middleware
# -------------------------------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "base.middleware.MultiCompanyMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# -------------------------------------------------
# URLs / WSGI
# -------------------------------------------------
ROOT_URLCONF = "Qms.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "base.context_processors.company",
            ],
        },
    },
]

WSGI_APPLICATION = "Qms.wsgi.application"


# -------------------------------------------------
# Auth
# -------------------------------------------------
AUTH_USER_MODEL = "base.User"

# مدة صلاحية توكن التفعيل واستعادة كلمة المرور (48 ساعة)
PASSWORD_RESET_TIMEOUT = 48 * 60 * 60  # 172800 ثانية

# Object-level permissions (django-guardian)
# الفائدة: إخبار Django باستخدام Backend الخاص بـ Guardian للتحقق من صلاحيات الكائن الواحد وليس الموديل فقط.
AUTHENTICATION_BACKENDS = (
    "django.contrib.auth.backends.ModelBackend",
    "guardian.backends.ObjectPermissionBackend",
)

# اسم المستخدم المجهول الذي يستخدمه guardian
# مستخدم خاص تمثّله الحزمة ليحمل صلاحيات كائنية (object-level) لزوّار غير مسجّلين.
# أنظمة الموارد البشرية عادة مغلقة على موظفين مسجّلين، ولا يوجد محتوى عام بلا تسجيل. إذن، لا حاجة عملية له.
# بهذه الحالة، لن تُنشئ الحزمة مستخدمًا مجهولًا ولن تحاول استخدامه.
ANONYMOUS_USER_NAME = None

# Auth redirects
# إذا حاول فتح أي رابط مباشر بدون تسجيل الدخول → يتحول تلقائيًا لصفحة تسجيل الدخول.
LOGIN_URL = "users/login/"
LOGIN_REDIRECT_URL = "/"        # بعد تسجيل الدخول نرجّعك للـ Home
LOGOUT_REDIRECT_URL = "users/login/"

# -------------------------------------------------
# Password validation
# -------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# -------------------------------------------------
# I18N / TZ
# -------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Baghdad"
USE_I18N = True
USE_TZ = True

# -------------------------------------------------
# Static & Media
# -------------------------------------------------
# عند التطوير: تستعمل staticfiles/ و media/.
# عند النشر: تستخدم python manage.py collectstatic → يضع كل الملفات في static_collected/ (جاهز للسيرفر)
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"   # ملفات التطوير
STATICFILES_DIRS = [BASE_DIR / "static"]   # مكان التجميع النهائي (production)

# Media files (ملفات يرفعها المستخدم مثل الصور والوثائق)
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# -------------------------------------------------
# Tailwind
# -------------------------------------------------
TAILWIND_APP_NAME = "theme"

# -------------------------------------------------
# Dev helpers
# -------------------------------------------------
if DEBUG:
    INSTALLED_APPS += ["django_browser_reload"]
    MIDDLEWARE += ["django_browser_reload.middleware.BrowserReloadMiddleware"]
