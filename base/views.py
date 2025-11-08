from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Q
from django.views import View
from django.views.generic import TemplateView, FormView, CreateView, DetailView, UpdateView
from django.apps import apps
from urllib.parse import urljoin
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout, get_user_model, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.shortcuts import render, redirect, get_object_or_404
from django.template.loader import render_to_string
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from base.forms import CompanySwitchForm, RegisterForm, PartnerForm, LoginForm, ProfileEditForm, UserForm, CompanyForm, \
    UserCreateForm
from base.tokens import account_activation_token
from .company_context import get_company_id, get_allowed_company_ids
from .models import Partner, Company
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from base.company_context import get_allowed_company_ids, get_company_id
from django.utils.timezone import now
from datetime import timedelta


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

#------- Auth & Profile views ---------

def register_view(request):
    if request.user.is_authenticated:
        return redirect("base:home")
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
        return redirect("base:home")
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
        return redirect(next_url or "base:home")
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


#------- dashboard views ---------

class HomeView(LoginRequiredMixin, TemplateView):
    template_name = "home.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        Company = apps.get_model("base", "Company")
        Partner = apps.get_model("base", "Partner")
        User = apps.get_model("base", "User")

        # اقرأ الشركة النشطة من الميدلوير (تم حقنها على request)
        current_company = None
        cid = getattr(self.request, "company_id", None)
        if cid:
            current_company = Company.objects.filter(id=cid).first()
        ctx["current_company"] = current_company

        # الشركات المسموح بها = الشركات المربوطة بالمستخدم (Odoo-like Allowed Companies)
        allowed_companies = self.request.user.companies.all()
        # الشركات النشطة (من الميدلوير) مع fallback للمسموح بها
        active_ids = getattr(self.request, "allowed_company_ids", None) or list(
            allowed_companies.values_list("id", flat=True))

        _pks = Partner.objects.with_acl("view").values("pk")
        partners_qs = (
            Partner.objects
            .filter(pk__in=_pks, company_id__in=active_ids)  # ✅ تقييد بالشركات النشطة
            .select_related("company", "parent")
        )

        _u_pks = User.acl_objects.with_acl("view").values("pk")
        users_qs = (
            User.objects
            .filter(pk__in=_u_pks, company_id__in=active_ids)  # ✅ تقييد بالشركات النشطة
            .select_related("company", "partner")
        )

        ctx.update({
            "companies_count": allowed_companies.count(),
            "partners_count": partners_qs.count(),
            "users_count": users_qs.count(),
            "recent_partners": partners_qs.order_by("-id")[:8],
            "recent_users": users_qs.order_by("-date_joined")[:8] if hasattr(User,
                                                                             "date_joined") else users_qs.order_by(
                "-id")[:8],
            "recent_companies": allowed_companies.order_by("-id")[:9],
        })
        return ctx

#------- company views ---------

class CompanySwitchView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        user = request.user
        # المسموح بها للمستخدم
        allowed_ids = set(user.companies.values_list("id", flat=True))
        is_super = bool(getattr(user, "is_superuser", False))

        # الشركات المحددة من الـNavbar
        selected = request.POST.getlist("active_companies")
        try:
            selected = [int(x) for x in selected]
        except Exception:
            selected = []

        # قيدها بالمسموح (إلا السوبر)
        if not is_super:
            selected = [cid for cid in selected if cid in allowed_ids]

        # fallback: لو ما اختار شيء → الشركة الافتراضية
        if not selected:
            default_id = getattr(user, "company_id", None)
            if default_id:
                selected = [default_id]
            else:
                messages.error(request, "You must select at least one company.")
                return redirect(request.META.get("HTTP_REFERER", reverse("base:home")))

        # الشركة الحالية القادمة من الـNavbar أو أول واحدة
        current_company = request.POST.get("current_company")
        try:
            current_company = int(current_company) if current_company else selected[0]
        except Exception:
            current_company = selected[0]

        # تأكد أن current ضمن النشطة
        if current_company not in selected:
            selected.insert(0, current_company)

        # خزّن في الجلسة
        request.session["active_company_ids"] = selected
        request.session["current_company_id"] = current_company

        messages.success(request, "Active companies updated.")
        return redirect(request.META.get("HTTP_REFERER", reverse("base:home")))

    # GET غير مستخدم (نرجع للصفحة الرئيسية)
    def get(self, request, *args, **kwargs):
        return redirect(reverse("base:home"))


#------- BaseScopedListView ---------

class CompanyScopeAclMixin:
    """
    يطبّق:
    - ACL per-record/per-model عبر with_acl('<perm>')
    - Company Scope عبر active_company_ids (مثل Odoo)
    - فلترة الحقول العلائقية في النماذج حسب الشركة المفعّلة
    """

    # اسم حقل الشركة على الموديل
    company_field_name = "company_id"

    # الصلاحية المطلوبة (list: view, detail: view, forms: change)
    required_acl_perm = "view"

    # -------- أدوات مشتركة --------
    def _active_company_ids(self):
        return get_allowed_company_ids(self.request)

    def _enforce_company_on_queryset(self, qs):
        active_ids = self._active_company_ids()
        if not active_ids:
            return qs.none()

        # Normalize to ORM FK name (e.g., "company_id" -> "company")
        orm_field = self.company_field_name[:-3] if self.company_field_name.endswith("_id") else self.company_field_name

        has_company = any(
            (getattr(f, "name", None) == orm_field) or (getattr(f, "attname", None) == f"{orm_field}_id")
            for f in qs.model._meta.get_fields()
        )
        if has_company:
            return qs.filter(**{f"{orm_field}__in": active_ids})
        return qs

    def _apply_acl_on_queryset(self, qs, perm=None):
        """
        أعد دائمًا QuerySet قابلًا للتصفية حتى لو كانت with_acl تُنشئ combined query.
        نأخذ Pks من with_acl ثم نفلتر عليها (pk__in) لتفادي union().
        """
        perm = perm or self.required_acl_perm

        # حالة: with_acl على الـ manager
        if hasattr(qs.model, "objects") and hasattr(qs.model.objects, "with_acl"):
            acl_qs = qs.model.objects.with_acl(perm)
            return qs.model.objects.filter(pk__in=acl_qs.values("pk"))

        # حالة: with_acl على الـ queryset نفسه
        if hasattr(qs, "with_acl"):
            acl_qs = qs.with_acl(perm)
            return qs.model.objects.filter(pk__in=acl_qs.values("pk"))

        return qs

    def _enforce_object_scope_or_404(self, obj):
        # فحص الشركة
        active_ids = self._active_company_ids()
        if hasattr(obj, self.company_field_name):
            comp_id = getattr(obj, self.company_field_name + "_id", None) or getattr(obj, self.company_field_name, None)
            comp_id = getattr(comp_id, "pk", comp_id)
            if active_ids and comp_id not in active_ids:
                raise Http404("Not found.")  # مثل Odoo يخفي السجل من خارج النطاق

        # فحص ACL per-record (إن وُجدت)
        if hasattr(obj, "check_acl"):
            if not obj.check_acl(self.request.user, self.required_acl_perm):
                raise PermissionDenied("Access denied.")
        return obj

    # -------- فلترة الحقول في النماذج --------
    def _filter_form_related_fields_by_company(self, form):
        """
        لأي Field فيه queryset وموديله يحتوي company_id → فلتره على الشركات المفعّلة.
        """
        active_ids = self._active_company_ids()
        if not active_ids:
            return

        for name, field in form.fields.items():
            qs = getattr(field, "queryset", None)
            if qs is None:
                continue
            model = getattr(qs, "model", None)
            if not model:
                continue
            if any(f.name == self.company_field_name for f in model._meta.get_fields()):
                field.queryset = qs.filter(**{f"{self.company_field_name}__in": active_ids})

    # -------- Defaults في الإنشاء --------
    def _set_default_company_on_create(self, form):
        """
        إذا كان الموديل يحتوي company_id ولم تُضبط، اضبطها على current_company_id.
        """
        if hasattr(form.instance, self.company_field_name) and not getattr(form.instance, self.company_field_name + "_id", None):
            current_id = get_company_id(self.request)
            if current_id:
                setattr(form.instance, self.company_field_name + "_id", current_id)


class BaseScopedListView(CompanyScopeAclMixin, ListView):
    required_acl_perm = "view"

    def get_queryset(self):
        qs = super().get_queryset()
        qs = self._apply_acl_on_queryset(qs, perm="view")
        qs = self._enforce_company_on_queryset(qs)
        return qs


class BaseScopedDetailView(CompanyScopeAclMixin, DetailView):
    required_acl_perm = "view"

    def get_queryset(self):
        qs = super().get_queryset()
        qs = self._apply_acl_on_queryset(qs, perm="view")
        qs = self._enforce_company_on_queryset(qs)
        return qs

    def get_object(self, queryset=None):
        obj = super().get_object(queryset=queryset)
        return self._enforce_object_scope_or_404(obj)


class BaseScopedCreateView(CompanyScopeAclMixin, CreateView):
    required_acl_perm = "change"

    def get_queryset(self):
        qs = super().get_queryset()
        qs = self._apply_acl_on_queryset(qs, perm="change")
        qs = self._enforce_company_on_queryset(qs)
        return qs

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        self._filter_form_related_fields_by_company(form)
        return form

    def form_valid(self, form):
        # ACL على الموديل (change) قبل الحفظ
        qs = self._apply_acl_on_queryset(self.model.objects.all(), perm="change")
        # ضبط الشركة الافتراضية
        self._set_default_company_on_create(form)
        # تأكيد أن الشركة ضمن النطاق
        if hasattr(form.instance, self.company_field_name):
            comp_id = getattr(form.instance, self.company_field_name + "_id", None)
            if comp_id and comp_id not in self._active_company_ids():
                raise PermissionDenied("Company is outside active scope.")
        return super().form_valid(form)


class BaseScopedUpdateView(CompanyScopeAclMixin, UpdateView):
    required_acl_perm = "change"

    def get_queryset(self):
        qs = super().get_queryset()
        qs = self._apply_acl_on_queryset(qs, perm="change")
        qs = self._enforce_company_on_queryset(qs)
        return qs

    def get_object(self, queryset=None):
        obj = super().get_object(queryset=queryset)
        # تحقق ACL per-record + company
        return self._enforce_object_scope_or_404(obj)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        self._filter_form_related_fields_by_company(form)
        return form

    def form_valid(self, form):
        # تأكيد أن الشركة بقيت ضمن النطاق
        if hasattr(form.instance, self.company_field_name):
            comp_id = getattr(form.instance, self.company_field_name + "_id", None)
            if comp_id and comp_id not in self._active_company_ids():
                raise PermissionDenied("Company is outside active scope.")
        # تحقق ACL per-record بعد أي تعديل
        if hasattr(form.instance, "check_acl"):
            if not form.instance.check_acl(self.request.user, "change"):
                raise PermissionDenied("Access denied.")
        return super().form_valid(form)


def _model_has_field(model, name: str) -> bool:
    return any(getattr(f, "name", None) == name or getattr(f, "attname", None) == name for f in model._meta.get_fields())

def _first_existing_field(model, candidates):
    for name in candidates:
        if _model_has_field(model, name):
            return name
    return None

def apply_search_filters(request, qs, search_fields=None):
    model = qs.model

    # ---- نص البحث ----
    q = (request.GET.get("q") or "").strip()
    if q and search_fields:
        cond = Q()
        for f in search_fields:
            cond |= Q(**{f"{f}__icontains": q})
        qs = qs.filter(cond)

    # ---- الشركة ----
    company_id = (request.GET.get("company") or "").strip()
    if company_id:
        # التعامل مع company أو company_id
        field = "company" if _model_has_field(model, "company_id") else ("company_id" if _model_has_field(model, "company_id") else None)
        if field:
            qs = qs.filter(**{field: company_id})

    # ---- Quick range ----
    rng = (request.GET.get("range") or "").strip()
    date_field = _first_existing_field(model, ("created_at", "date_joined"))
    if rng and date_field:
        today = now().date()
        if rng == "today":
            qs = qs.filter(**{f"{date_field}__date": today})
        elif rng == "week":
            start = today - timedelta(days=today.weekday())
            qs = qs.filter(**{f"{date_field}__date__gte": start})
        elif rng == "month":
            qs = qs.filter(**{f"{date_field}__year": today.year, f"{date_field}__month": today.month})
        elif rng == "year":
            qs = qs.filter(**{f"{date_field}__year": today.year})

    # ---- Active (عام) ----
    active = (request.GET.get("active") or "").strip()
    # يدعم active أو is_active تلقائيًا
    active_field = _first_existing_field(model, ("active", "is_active"))
    if active in ("0", "1") and active_field:
        qs = qs.filter(**{active_field: active == "1"})

    # ---- Kind (Partner فقط) ----
    kind = (request.GET.get("kind") or "").strip()
    if model._meta.model_name == "partner" and kind in ("company", "person"):
        qs = qs.filter(company_type=kind)

    # ---- Date from/to (على created_at أو date_joined) ----
    date_from = (request.GET.get("date_from") or "").strip()
    date_to   = (request.GET.get("date_to") or "").strip()
    if date_field and (date_from or date_to):
        if date_from:
            qs = qs.filter(**{f"{date_field}__date__gte": date_from})
        if date_to:
            qs = qs.filter(**{f"{date_field}__date__lte": date_to})

    return qs


#------- partner views ---------

class PartnerListView(LoginRequiredMixin, BaseScopedListView):
    model = Partner
    paginate_by = 20
    template_name = "base/partner_list.html"

    def get_queryset(self):
        # super() يطبق: with_acl("view") + نطاق الشركات عبر الميكسن
        base_qs = super().get_queryset()
        qs = (
            base_qs
            .select_related("company", "parent")
            .order_by("name")
        )
        qs = apply_search_filters(self.request, qs, search_fields=["name", "email", "phone"])
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["list_model"] = self.model._meta.model_name  # مهم للـKind filter
        # زر +New Partner (perms Django)
        ctx["can_add_partner"] = self.request.user.has_perm("base.add_partner")
        # أزرار Edit حسب ACL per-record
        change_ids = self.model.objects.with_acl("change").values_list("id", flat=True)
        ctx["partner_change_ids"] = set(change_ids)
        return ctx

class PartnerUpdateView(LoginRequiredMixin, BaseScopedUpdateView):
    model = Partner
    form_class = PartnerForm
    template_name = "base/partner_form.html"
    success_url = reverse_lazy("base:partner_list")

    def get_queryset(self):
        base_qs = super().get_queryset()
        _pks = base_qs.with_acl("change").values("pk")
        return base_qs.model.objects.filter(pk__in=_pks).select_related("company", "parent")

class PartnerCreateView(LoginRequiredMixin, PermissionRequiredMixin, BaseScopedCreateView):
    model = Partner
    form_class = PartnerForm
    template_name = "base/partner_form.html"
    success_url = reverse_lazy("base:partner_list")
    permission_required = "base.add_partner"

    def get_initial(self):
        init = super().get_initial()
        # اضبط الشركة الحالية افتراضيًا
        if not init.get("company"):
            cid = get_company_id()
            if cid:
                init["company"] = cid
        return init

class PartnerDetailView(LoginRequiredMixin, BaseScopedDetailView):
    model = Partner
    template_name = "base/partner_detail.html"

    def get_queryset(self):
        # super() يطبق ACL + Company Scope بعد تعديل _apply_acl_on_queryset
        return super().get_queryset().select_related("company", "parent")

    def get_context_data(self, **kwargs):
        from base.acl_service import has_perm
        ctx = super().get_context_data(**kwargs)
        obj = ctx.get("object")
        ctx["can_edit_object"] = bool(obj and has_perm(self.request.user, obj, "change"))
        return ctx


# --- Users ---
class UserListView(LoginRequiredMixin, BaseScopedListView):
    model = User
    template_name = "base/user_list.html"
    paginate_by = 24

    def get_queryset(self):
        base = self.model.acl_objects.with_acl("view")
        qs = (self.model.objects
              .filter(pk__in=base.values("pk"))
              .select_related("company")
              .prefetch_related("companies")
              .order_by("email"))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["list_model"] = self.model._meta.model_name  # مهم للـKind filter
        from django.contrib.auth import get_user_model
        UserModel = get_user_model()
        ctx["can_add_user"] = self.request.user.has_perm(f"{UserModel._meta.app_label}.add_{UserModel._meta.model_name}")
        change_ids = User.acl_objects.with_acl("change").values_list("id", flat=True)
        ctx["user_change_ids"] = set(change_ids)
        return ctx

class UserDetailView(LoginRequiredMixin, BaseScopedDetailView):
    model = User
    template_name = "base/user_detail.html"

    def get_queryset(self):
        _pks = User.acl_objects.with_acl("view").values("pk")
        return User.objects.filter(pk__in=_pks).select_related("company", "partner")

    def get_context_data(self, **kwargs):
        from base.acl_service import has_perm
        ctx = super().get_context_data(**kwargs)
        obj = ctx.get("object")
        ctx["can_edit_object"] = bool(obj and has_perm(self.request.user, obj, "change"))
        return ctx

class UserUpdateView(LoginRequiredMixin, BaseScopedUpdateView):
    model = User
    form_class = UserForm
    template_name = "base/users/user_form.html"
    success_url = reverse_lazy("base:user_list")

    def get_queryset(self):
        _pks = User.acl_objects.with_acl("change").values("pk")
        return User.objects.filter(pk__in=_pks).select_related("company", "partner")

class UserCreateView(LoginRequiredMixin, PermissionRequiredMixin, BaseScopedCreateView):
    model = User
    form_class = UserCreateForm          # موجود عندك في forms.py
    template_name = "base/user_form.html"
    success_url = reverse_lazy("base:user_list")
    permission_required = "base.add_user"

    def get_initial(self):
        init = super().get_initial()
        # اضبط الشركة الحالية افتراضيًا (إن توفرت)
        from .company_context import get_company_id
        cid = get_company_id(self.request)
        if cid and "company" in self.form_class().fields:
            init["company"] = cid
        return init

# --- Companies ---
class CompanyListView(LoginRequiredMixin, BaseScopedListView):
    model = Company
    template_name = "base/company_list.html"
    paginate_by = 24

    def get_queryset(self):
        # super() يطبق with_acl("view") + نطاق الشركات
        base_qs = super().get_queryset()
        qs = base_qs.order_by("name")
        qs = apply_search_filters(self.request, qs, search_fields=["name"])
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["list_model"] = self.model._meta.model_name  # مهم للـKind filter
        ctx["can_add_company"] = self.request.user.has_perm("base.add_company")
        change_ids = self.model.objects.with_acl("change").values_list("id", flat=True)
        ctx["company_change_ids"] = set(change_ids)
        return ctx

class CompanyDetailView(LoginRequiredMixin, BaseScopedDetailView):
    model = Company
    template_name = "base/company_detail.html"

    def get_queryset(self):
        base_qs = super().get_queryset()
        _pks = base_qs.with_acl("view").values("pk")
        return Company.objects.filter(pk__in=_pks)

    def get_context_data(self, **kwargs):
        from base.acl_service import has_perm
        ctx = super().get_context_data(**kwargs)
        obj = ctx.get("object")
        ctx["can_edit_object"] = bool(obj and has_perm(self.request.user, obj, "change"))
        return ctx

class CompanyUpdateView(LoginRequiredMixin, BaseScopedUpdateView):
    model = Company
    form_class = CompanyForm            # سنضيفه بالخطوة 2
    template_name = "base/company_form.html"
    success_url = reverse_lazy("base:company_list")

    def get_queryset(self):
        base_qs = super().get_queryset()
        _pks = base_qs.with_acl("change").values("pk")
        return Company.objects.filter(pk__in=_pks)

class CompanyCreateView(LoginRequiredMixin, PermissionRequiredMixin, BaseScopedCreateView):
    model = Company
    form_class = CompanyForm
    template_name = "base/company_form.html"
    success_url = reverse_lazy("base:company_list")
    permission_required = "base.add_company"

