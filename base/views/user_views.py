from urllib.parse import urljoin

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, get_user_model, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.shortcuts import render, redirect, get_object_or_404
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode

from ..forms import RegisterForm, LoginForm, ProfileEditForm
from ..tokens import account_activation_token

User = get_user_model()

# ===== Helpers =====
def _send_activation_email(request, user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = account_activation_token.make_token(user)
    path = reverse("base:activate", args=[uid, token])

    base = getattr(settings, "SITE_URL", "") or request.build_absolute_uri("/")
    base = base.strip().rstrip("/") + "/"
    activate_url = urljoin(base, path.lstrip("/"))

    ctx = {"user": user, "activate_url": activate_url}
    subject = render_to_string("base/users/emails/activation_subject.txt", ctx).strip()
    text_body = render_to_string("base/users/emails/activation_email.txt", ctx)
    html_body = render_to_string("base/users/emails/activation_email.html", ctx)

    from django.core.mail import EmailMultiAlternatives
    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
        headers={"Reply-To": settings.DEFAULT_FROM_EMAIL},
    )
    msg.attach_alternative(html_body, "text/html")
    msg.send(fail_silently=False)

# ===== Auth & Profile =====
def register_view(request):
    if request.user.is_authenticated:
        return redirect("home")  # تعديل طفيف ليتسق مع توجيهنا الافتراضي
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        try:
            _send_activation_email(request, user)
            request.session["last_activation_email"] = user.email  # <-- إضافة جديدة
            messages.success(request, "We sent you an activation link. Please check your email.")
            return redirect("base:activation_sent")
        except Exception:
            messages.error(request, "Could not send activation email. Please try again.")
            return redirect("base:activation_failed")
    return render(request, "base/users/register.html", {"form": form})

def activate_view(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except Exception:
        user = None

    if not user:
        messages.error(request, "Invalid activation link.")
        return redirect("base:activation_failed")

    if user.is_active and getattr(user, "email_verified", False):
        messages.info(request, "This account is already activated.")
        return redirect("base:login")

    if account_activation_token.check_token(user, token):
        update_fields = []
        if not user.is_active:
            user.is_active = True
            update_fields.append("is_active")
        if hasattr(user, "email_verified"):
            user.email_verified = True
            user.email_verified_at = timezone.now()
            update_fields += ["email_verified", "email_verified_at"]
        user.save(update_fields=update_fields or None)
        messages.success(request, "Your account has been activated successfully. You can login now.")
        return render(request, "base/users/activation_success.html")

    messages.error(request, "Invalid or expired activation link. Please request a new one.")
    return redirect("base:resend_activation")

def resend_activation_view(request):
    if request.method == "POST":
        email = (request.POST.get("email") or "").strip()
        if not email:
            messages.error(request, "Please provide your email.")
            return redirect("base:activation_failed")
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            messages.error(request, "No account found with this email.")
            return redirect("base:activation_failed")
        try:
            _send_activation_email(request, user)
            request.session["last_activation_email"] = user.email  # <-- إضافة جديدة
            messages.success(request, "A new activation link has been sent to your email.")
            return redirect("base:activation_sent")
        except Exception:
            messages.error(request, "Could not send activation email. Please try again later.")
            return redirect("base:activation_failed")
    return render(request, "base/users/resend_activation.html")

def activation_sent_view(request):
    # خذ الإيميل من الجلسة (واحتفظ به أو احذفه حسب رغبتك)
    email = request.session.get("last_activation_email")
    return render(request, "base/users/activation_sent.html", {"email": email})


def activation_failed_view(request):
    return render(request, "base/users/activation_failed.html")

def login_view(request):
    if request.user.is_authenticated:
        return redirect("home")
    form = LoginForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.get_user()

        # إنهاء جلسة قديمة إن وُجدت
        if getattr(user, "last_session_key", None):
            from django.contrib.sessions.models import Session
            try:
                Session.objects.get(session_key=user.last_session_key).delete()
            except Session.DoesNotExist:
                pass

        login(request, user)
        user.last_session_key = request.session.session_key
        user.save(update_fields=["last_session_key"])

        # === Multi-company bootstrapping ===
        allowed_ids = list(user.companies.values_list("id", flat=True))
        current_id = getattr(user, "company_id", None)
        if current_id not in allowed_ids:
            current_id = allowed_ids[0] if allowed_ids else None

        # فعّل شركة واحدة افتراضيًا (يمكن للمستخدم تغيير/توسيع الاختيار من شاشة switch)
        request.session["active_company_ids"] = [current_id] if current_id else []
        request.session["current_company_id"] = current_id

        # إعادة التوجيه
        next_url = request.GET.get("next") or request.POST.get("next")
        return redirect(next_url or "home")
    return render(request, "base/users/login.html", {"form": form})

def logout_view(request):
    # نظّف مفاتيح العزل متعددة الشركات
    request.session.pop("active_company_ids", None)
    request.session.pop("current_company_id", None)

    if request.user.is_authenticated:
        request.user.last_session_key = None
        request.user.save(update_fields=["last_session_key"])
    logout(request)
    messages.info(request, "Logged out.")
    return redirect("base:login")

@login_required
def profile_view(request):
    return render(request, "base/users/profile.html")

@login_required
def edit_profile_view(request):
    form = ProfileEditForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profile updated.")
        return redirect("base:profile")
    return render(request, "base/users/edit_profile.html", {"form": form})

@login_required
def password_change_view(request):
    form = PasswordChangeForm(user=request.user, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        # إبقاء الجلسة فعّالة بعد تغيير كلمة السر
        update_session_auth_hash(request, user)
        messages.success(request, "Your password has been changed successfully.")
        return redirect("base:password_change_done")
    return render(request, "base/users/password_change.html", {"form": form})

@login_required
def password_change_done_view(request):
    return render(request, "base/users/password_change_done.html")

@login_required
def home_view(request):
    # أي سياق إضافي للوحة البداية
    return render(request, "home.html")
