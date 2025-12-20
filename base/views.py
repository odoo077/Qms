# base/views.py

from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Q
from django.views import View
from django.views.generic import TemplateView, FormView, CreateView, DetailView, UpdateView, DeleteView
from django.apps import apps
from urllib.parse import urljoin
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout, get_user_model, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.shortcuts import render, redirect
from django.template.loader import render_to_string
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from base.forms import RegisterForm, PartnerForm, LoginForm, ProfileEditForm, UserForm, CompanyForm, \
    UserCreateForm
from base.tokens import account_activation_token
from .acl_service import has_perm
from .models import Partner, Company
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
    form = ProfileEditForm(
        request.POST or None,
        request.FILES or None,
        instance=request.user
    )
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


# ------------------------------------------------------------
# Dashboard
# ------------------------------------------------------------
class HomeView(LoginRequiredMixin, TemplateView):
    template_name = "home.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        Company = apps.get_model("base", "Company")
        Partner = apps.get_model("base", "Partner")
        User = apps.get_model("base", "User")

        # الشركة الحالية (محقونة من middleware)
        current_company = None
        cid = getattr(self.request, "company_id", None)
        if cid:
            current_company = Company.objects.filter(id=cid).first()
        ctx["current_company"] = current_company

        # الشركات المسموح بها للمستخدم
        allowed_companies = self.request.user.companies.all()

        # الشركات النشطة (Odoo-like)
        active_ids = (
            getattr(self.request, "allowed_company_ids", None)
            or list(allowed_companies.values_list("id", flat=True))
        )

        # Partners (ACL + Company scope)
        partner_pks = Partner.objects.with_acl("view").values_list("pk", flat=True)
        partners_qs = (
            Partner.objects
            .filter(pk__in=partner_pks, company_id__in=active_ids)
            .select_related("company", "parent")
        )

        # Users (ACL + Company scope)
        user_pks = User.acl_objects.with_acl("view").values_list("pk", flat=True)
        users_qs = (
            User.objects
            .filter(pk__in=user_pks, company_id__in=active_ids)
            .select_related("company", "partner")
        )

        ctx.update({
            "companies_count": allowed_companies.count(),
            "partners_count": partners_qs.count(),
            "users_count": users_qs.count(),
            "recent_partners": partners_qs.order_by("-id")[:8],
            "recent_users": (
                users_qs.order_by("-date_joined")[:8]
                if hasattr(User, "date_joined")
                else users_qs.order_by("-id")[:8]
            ),
            "recent_companies": allowed_companies.order_by("-id")[:9],
        })
        return ctx


# ------------------------------------------------------------
# Company Switch (Multi-company like Odoo)
# ------------------------------------------------------------
class CompanySwitchView(LoginRequiredMixin, View):

    def post(self, request, *args, **kwargs):
        """
        تبديل الشركات النشطة (Multi-company switch) على نمط Odoo.

        المسؤوليات:
        - التحقق من الشركات المسموح بها للمستخدم
        - ضبط الشركات النشطة (active_company_ids)
        - تحديد الشركة الحالية (current_company_id)
        - مزامنة Session + ContextVar فورًا
        """

        user = request.user

        # -------------------------------------------------
        # 1) تحديد الشركات المسموح بها للمستخدم
        # -------------------------------------------------
        allowed_ids = set(user.companies.values_list("id", flat=True))
        is_super = bool(getattr(user, "is_superuser", False))

        # -------------------------------------------------
        # 2) قراءة الشركات المختارة من الواجهة
        # -------------------------------------------------
        try:
            selected = [int(x) for x in request.POST.getlist("active_companies")]
        except Exception:
            selected = []

        # -------------------------------------------------
        # 3) تقييد الاختيار بالشركات المسموح بها
        #    (إلا في حالة superuser)
        # -------------------------------------------------
        if not is_super:
            selected = [cid for cid in selected if cid in allowed_ids]

        # -------------------------------------------------
        # 4) fallback: إن لم يُحدَّد شيء
        #    استخدم الشركة الافتراضية للمستخدم
        # -------------------------------------------------
        if not selected:
            default_id = getattr(user, "company_id", None)
            if default_id:
                selected = [default_id]
            else:
                messages.error(request, "You must select at least one company.")
                return redirect(request.META.get("HTTP_REFERER", reverse("base:home")))

        # -------------------------------------------------
        # 5) تحديد الشركة الحالية (current company)
        # -------------------------------------------------
        try:
            current_company = int(request.POST.get("current_company"))
        except Exception:
            current_company = selected[0]

        # تأكد أن الشركة الحالية ضمن الشركات النشطة
        if current_company not in selected:
            selected.insert(0, current_company)

        # -------------------------------------------------
        # 6) التخزين في الجلسة (Session)
        #    تعتمد عليه middleware + requests القادمة
        # -------------------------------------------------
        request.session["active_company_ids"] = selected
        request.session["current_company_id"] = current_company

        # -------------------------------------------------
        # 7) مزامنة ContextVar فورًا
        #    (منع تعارض نفس الطلب / redirect)
        # -------------------------------------------------
        from base.company_context import set_company
        set_company(current_company, selected)

        # -------------------------------------------------
        # 8) رسالة نجاح + إعادة توجيه
        # -------------------------------------------------
        messages.success(request, "Active companies updated.")
        return redirect(request.META.get("HTTP_REFERER", reverse("base:home")))

    def get(self, request, *args, **kwargs):
        # GET غير مستخدم
        return redirect(reverse("base:home"))



# ------------------------------------------------------------
# Company + ACL Scope Mixin (Odoo-like Record Rules)
# ------------------------------------------------------------
class CompanyScopeAclMixin:
    """
    يطبّق:
    - ACL per-record عبر base.acl_service.has_perm
    - Company scope عبر active_company_ids
    - فلترة الحقول العلائقية في النماذج حسب الشركة
    """

    # الصحيح: اسم الحقل في الموديلات هو company (ويُشتق منه company_id تلقائيًا)
    company_field_name = "company"
    required_acl_perm = "view"

    # ---------- Helpers ----------
    def _active_company_ids(self):
        return get_allowed_company_ids(self.request)

    def _enforce_company_on_queryset(self, qs):
        """
        يقيّد queryset بالشركات النشطة (active_company_ids).
        - موديل Company نفسه: filter(id__in=active_ids)
        - أي موديل فيه FK اسمها company: filter(company__in=active_ids)
        """
        active_ids = self._active_company_ids()
        if not active_ids:
            return qs.none()

        # حالة موديل Company نفسه
        if qs.model._meta.app_label == "base" and qs.model._meta.model_name == "company":
            return qs.filter(id__in=active_ids)

        # إذا كان بالموديل FK اسمها company
        if any(f.name == self.company_field_name for f in qs.model._meta.fields):
            return qs.filter(**{f"{self.company_field_name}__in": active_ids})

        return qs

    def _apply_acl_on_queryset(self, qs, perm=None):
        """
        يطبق ACL على مستوى queryset عبر managers:
        - Model.acl_objects.with_acl(perm)
        - أو Model.objects.with_acl(perm)
        """
        perm = perm or self.required_acl_perm
        Model = qs.model

        acl_mgr = getattr(Model, "acl_objects", None)
        if hasattr(acl_mgr, "with_acl"):
            allowed = acl_mgr.with_acl(perm).values_list("pk", flat=True)
            return Model.objects.filter(pk__in=allowed)

        if hasattr(Model.objects, "with_acl"):
            allowed = Model.objects.with_acl(perm).values_list("pk", flat=True)
            return Model.objects.filter(pk__in=allowed)

        return qs

    def _enforce_object_scope_or_404(self, obj):
        """
        يفحص:
        1) Company scope على السجل نفسه (company_id ضمن active_company_ids)
        2) ACL per-record عبر has_perm(user, obj, perm)
        """
        # 1) Company scope
        active_ids = self._active_company_ids()
        if hasattr(obj, f"{self.company_field_name}_id"):
            cid = getattr(obj, f"{self.company_field_name}_id", None)
            if active_ids and cid not in active_ids:
                raise Http404("Not found")

        # 2) Object ACL (المصدر الحقيقي للصلاحيات عندك)
        if not has_perm(self.request.user, obj, self.required_acl_perm):
            raise PermissionDenied("Access denied")

        return obj

    # ---------- Forms ----------
    def _filter_form_related_fields_by_company(self, form):
        """
        يقيّد querysets للحقول العلائقية (FK/M2M) بحيث لا تعرض سجلات خارج الشركات النشطة.
        """
        active_ids = self._active_company_ids()
        if not active_ids:
            return

        for field in form.fields.values():
            qs = getattr(field, "queryset", None)
            if qs is None:
                continue

            model = getattr(qs, "model", None)
            if not model:
                continue

            # إذا كان الموديل المرتبط يملك company_id
            if any(f.name == f"{self.company_field_name}" for f in model._meta.fields):
                field.queryset = qs.filter(**{f"{self.company_field_name}__in": active_ids})

    def _set_default_company_on_create(self, form):
        """
        يضبط company_id تلقائيًا عند الإنشاء إن كان الحقل موجودًا وفارغًا.
        """
        if hasattr(form.instance, f"{self.company_field_name}_id"):
            if not getattr(form.instance, f"{self.company_field_name}_id", None):
                cid = get_company_id(self.request)
                if cid:
                    setattr(form.instance, f"{self.company_field_name}_id", cid)




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
        # تحقق ACL على مستوى الموديل قبل الإنشاء (Odoo-like)
        if hasattr(self.model, "acl_objects"):
            allowed = self.model.acl_objects.with_acl("change")
            if not allowed.exists():
                raise PermissionDenied("Access denied.")

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
        # تحقق ACL per-record (single source of truth)
        from base.acl_service import has_perm

        if not has_perm(self.request.user, form.instance, "change"):
            raise PermissionDenied("Access denied.")
        return super().form_valid(form)


class BaseScopedDeleteView(CompanyScopeAclMixin, DeleteView):
    """
    DeleteView مدمج مع صلاحيات الشركة + ACL
    - يطبق with_acl("delete") على مستوى الموديل
    - يقيّد النتائج بالشركات النشطة
    - يتحقق من ACL على السجل نفسه عبر _enforce_object_scope_or_404
    """
    required_acl_perm = "delete"

    def get_queryset(self):
        qs = super().get_queryset()
        qs = self._apply_acl_on_queryset(qs, perm="delete")
        qs = self._enforce_company_on_queryset(qs)
        return qs

    def get_object(self, queryset=None):
        obj = super().get_object(queryset=queryset)
        return self._enforce_object_scope_or_404(obj)


class ConfirmDeleteMixin:
    """
    صفحة تأكيد حذف موحّدة لكل المشروع.
    """
    template_name = "partials/confirm_delete.html"
    object_label_field = "name"   # يمكن تغييره في كل View
    back_url_name = None          # يجب تحديده في كل View
    confirm_label = "Yes, delete"

    def get_object_label(self):
        obj = self.object
        field = getattr(self, "object_label_field", None)
        if field and hasattr(obj, field):
            return getattr(obj, field)
        return str(obj)

    def get_back_url(self):
        name = getattr(self, "back_url_name", None)
        if name:
            return reverse(name)
        return None

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["object_label"] = self.get_object_label()
        ctx["back_url"] = self.get_back_url()
        ctx["confirm_label"] = self.confirm_label
        return ctx


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
        field = "company_id" if _model_has_field(model, "company_id") else None
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

class PartnerUpdateView(LoginRequiredMixin, UpdateView):
    """
    Partner Update View

    - Uses PartnerForm (identity & contact only)
    - No company scope
    - ACL enforced once on persisted object
    """

    model = Partner
    form_class = PartnerForm            # ✅ هذا هو الحل
    template_name = "base/partner_form.html"
    success_url = reverse_lazy("base:partner_list")

    def get_queryset(self):
        # ACL only — no company scope
        return Partner.objects.all()

    def get_object(self, queryset=None):
        obj = super().get_object(queryset=queryset)

        if not has_perm(obj, self.request.user, "change"):
            raise PermissionDenied("Access denied.")

        return obj

class PartnerCreateView(LoginRequiredMixin, PermissionRequiredMixin, BaseScopedCreateView):
    model = Partner
    form_class = PartnerForm
    template_name = "base/partner_form.html"
    success_url = reverse_lazy("base:partner_list")
    permission_required = "base.add_partner"

class PartnerDetailView(LoginRequiredMixin, DetailView):
    """
    Partner Detail View

    Design decisions:
    - NO Company Scope enforcement
    - NO ACL enforcement on view
    - Partner is a directory / identity object
    - ACL applies only to create / edit / delete
    """

    model = Partner
    template_name = "base/partner_detail.html"

    def get_queryset(self):
        """
        Partner records are readable for any authenticated user.
        """
        return Partner.objects.select_related("company", "parent")

    def get_context_data(self, **kwargs):
        """
        Expose edit permission safely to the template.
        """
        ctx = super().get_context_data(**kwargs)
        obj = ctx.get("object")

        ctx["can_edit_object"] = (
            bool(obj) and has_perm(obj, self.request.user, "change")
        )

        return ctx

# --- Users ---
class UserListView(LoginRequiredMixin, BaseScopedListView):
    model = User
    template_name = "base/user_list.html"
    paginate_by = 24

    def get_queryset(self):
        # احصل على Pks عبر ACL
        base_acl = self.model.acl_objects.with_acl("view").values("pk")
        qs = (self.model.objects
              .filter(pk__in=base_acl)
              .select_related("company")
              .prefetch_related("companies")
              .order_by("email"))
        # ✅ فلترة الشركة النشطة
        qs = self._enforce_company_on_queryset(qs)
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

class UserDetailView(LoginRequiredMixin, DetailView):
    model = User
    template_name = "base/user_detail.html"

    def get_queryset(self):
        """
        Users are directory objects.
        Visibility is controlled by ACL only, not company scope.
        """
        pks = User.acl_objects.with_acl("view").values_list("pk", flat=True)
        return User.objects.filter(pk__in=pks).select_related("company", "partner")

    def get_object(self, queryset=None):
        """
        Enforce ACL explicitly without company scope.
        """
        obj = super().get_object(queryset=queryset)

        from base.acl_service import has_perm

        # السماح للمستخدم برؤية نفسه دائمًا
        if obj.pk == self.request.user.pk:
            return obj

        # superuser / staff مسموح
        if self.request.user.is_superuser or self.request.user.is_staff:
            return obj

        # ACL لبقية الحالات
        if not has_perm(self.request.user, obj, "view"):
            raise PermissionDenied("Access denied.")

        return obj

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        obj = ctx.get("object")

        from base.acl_service import has_perm
        ctx["can_edit_object"] = bool(obj and has_perm(self.request.user, obj, "change"))
        return ctx


class UserUpdateView(LoginRequiredMixin, UpdateView):
    """
    User Update View

    Rules:
    - User can always edit himself
    - Admin / staff can edit any user
    - Others require explicit ACL (change)
    - NO company scope enforcement
    """

    model = User
    form_class = UserForm
    template_name = "base/user_form.html"
    success_url = reverse_lazy("base:user_list")

    def get_queryset(self):
        """
        Define the set of users that can be *resolved* by this view.

        Design principles:
        - User is NOT company-scoped.
        - Self-edit must ALWAYS be allowed.
        - Other users require explicit ACL permission (change).
        - Final permission enforcement is completed in get_object().
        """

        # --------------------------------------------------
        # 1) Users allowed by ACL (change)
        # --------------------------------------------------
        acl_ids = set(
            User.acl_objects
            .with_acl("change")
            .values_list("pk", flat=True)
        )

        # --------------------------------------------------
        # 2) Always allow the current user to be resolved
        #    (self-edit is guaranteed by design)
        # --------------------------------------------------
        acl_ids.add(self.request.user.pk)

        # --------------------------------------------------
        # 3) Build queryset without company scope
        # --------------------------------------------------
        return (
            User.objects
            .filter(pk__in=acl_ids)
            .select_related("company", "partner")
        )

    def get_object(self, queryset=None):
        obj = super().get_object(queryset=queryset)

        # 1) المستخدم يعدّل نفسه دائمًا
        if obj.pk == self.request.user.pk:
            return obj

        # 2) superuser / staff
        if self.request.user.is_superuser or self.request.user.is_staff:
            return obj

        # 3) ACL لبقية الحالات
        from base.acl_service import has_perm
        if not has_perm(self.request.user, obj, "change"):
            raise PermissionDenied("Access denied.")

        return obj

class UserCreateView(LoginRequiredMixin, PermissionRequiredMixin, BaseScopedCreateView):
    """
    User Create View

    Responsibilities:
    - Enforce permission: base.add_user
    - Pre-fill company & allowed companies from active company context
    - Create user safely
    - Rely on signals for:
        * Partner creation
        * Default ACL bootstrap
        * UserSettings initialization
    """

    model = User
    form_class = UserCreateForm
    template_name = "base/user_form.html"
    success_url = reverse_lazy("base:user_list")
    permission_required = "base.add_user"

    def get_initial(self):
        """
        Pre-fill company and allowed companies
        based on the currently active company.
        """
        initial = super().get_initial()

        from .company_context import get_company_id
        cid = get_company_id(self.request)

        if cid:
            if "company" in self.form_class.base_fields:
                initial["company"] = cid
            if "companies" in self.form_class.base_fields:
                initial["companies"] = [cid]

        return initial

    def form_invalid(self, form):
        """
        Never allow silent failure.
        Log errors explicitly for debugging.
        """
        print("❌ USER CREATE FORM ERRORS")
        print("Form errors:", form.errors)
        print("Non-field errors:", form.non_field_errors())
        return super().form_invalid(form)

    def form_valid(self, form):
        """
        Save user.

        IMPORTANT:
        - DO NOT grant ACL manually here
        - ACL is applied automatically via signals:
            post_save(User) -> apply_default_acl()
        """
        return super().form_valid(form)

# --- Companies ---
class CompanyListView(LoginRequiredMixin, BaseScopedListView):
    model = Company
    template_name = "base/company_list.html"
    paginate_by = 24

    def get_queryset(self):
        qs = super().get_queryset()
        qs = qs.order_by("name")
        qs = apply_search_filters(self.request, qs, search_fields=["name"])
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        ctx["list_model"] = self.model._meta.model_name
        ctx["can_add_company"] = self.request.user.has_perm("base.add_company")

        # ✅ استخدم نفس queryset المعروض
        change_ids = (
            self.get_queryset()
            .with_acl("change")
            .values_list("id", flat=True)
        )
        ctx["company_change_ids"] = set(change_ids)

        return ctx

class CompanyDetailView(LoginRequiredMixin, DetailView):
    """
    Company Detail View

    Rules:
    - NO Company Scope enforcement
    - ACL enforced explicitly (view)
    - Company is a structural object
    """

    model = Company
    template_name = "base/company_detail.html"

    def get_queryset(self):
        """
        Enforce ACL (view) only.
        NO company scope.
        """
        from base.acl_service import has_perm

        return (
            Company.objects
            .with_acl("view")
            .select_related("parent", "partner")
        )

    def get_context_data(self, **kwargs):
        from base.acl_service import has_perm

        ctx = super().get_context_data(**kwargs)
        obj = ctx.get("object")

        ctx["can_edit_object"] = (
            bool(obj) and has_perm(obj, self.request.user, "change")
        )
        return ctx

class CompanyUpdateView(LoginRequiredMixin, BaseScopedUpdateView):
    """
    Company Update View

    Why we override get_object():
    - BaseScopedUpdateView.get_object() يطبق Object-level ACL عبر _enforce_object_scope_or_404:contentReference[oaicite:4]{index=4}:contentReference[oaicite:5]{index=5}
    - Company كيان هيكلي (Directory/Root) وغالبًا لا يحتاج Object-level ACL على مستوى السجل
    - لذلك نعتمد على:
      1) Django permission: base.change_company
      2) Active company scope (الشركات النشطة فقط)
    """

    model = Company
    form_class = CompanyForm
    template_name = "base/company_form.html"
    success_url = reverse_lazy("base:company_list")

    def get_object(self, queryset=None):
        """
        Fetch object using Django's UpdateView logic (NOT BaseScopedUpdateView),
        then enforce:
        - Django permission
        - Active company scope
        """
        # 1) احصل على الشركة بدون المرور على BaseScopedUpdateView.get_object()
        obj = UpdateView.get_object(self, queryset=queryset)

        # 2) تحقق صلاحية Django القياسية
        # (هذه هي الصلاحية المنطقية لتعديل الشركات في Django)
        if not self.request.user.has_perm("base.change_company"):
            raise PermissionDenied("Access denied.")

        # 3) تحقق من نطاق الشركات النشطة (multi-company scope)
        active_ids = get_allowed_company_ids(self.request)
        if active_ids and obj.pk not in active_ids:
            raise PermissionDenied("Company is outside active scope.")

        return obj

    def form_valid(self, form):
        """
        نترك BaseScopedUpdateView.form_valid يعمل من حيث الحفظ،
        لكن بدون الاعتماد على Object-level ACL الخاص بالـ mixin (لأننا عالجناه في get_object)
        """

        # كإجراء إضافي: تأكيد أن الشركة لم تخرج من النطاق بعد التعديل
        active_ids = get_allowed_company_ids(self.request)
        if active_ids and form.instance.pk not in active_ids:
            raise PermissionDenied("Company is outside active scope.")

        return super().form_valid(form)

class CompanyCreateView(LoginRequiredMixin, PermissionRequiredMixin, BaseScopedCreateView):
    model = Company
    form_class = CompanyForm
    template_name = "base/company_form.html"
    success_url = reverse_lazy("base:company_list")
    permission_required = "base.add_company"


