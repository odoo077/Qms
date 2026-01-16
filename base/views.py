# base/views.py
from dataclasses import dataclass

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q, Count
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
from django.urls import reverse, reverse_lazy, NoReverseMatch
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from base.forms import RegisterForm, PartnerForm, LoginForm, ProfileEditForm, UserForm, CompanyForm, \
    UserCreateForm, UserFilterForm, PartnerFilterForm
from base.tokens import account_activation_token
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
            request.session["last_activation_email"] = user.email
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
            request.session["last_activation_email"] = user.email
            messages.success(request, "A new activation link has been sent to your email.")
            return redirect("base:activation_sent")
        except Exception:
            messages.error(request, "Could not send activation email. Please try again later.")
            return redirect("base:activation_failed")
    return render(request, "base/users/resend_activation.html")


def activation_sent_view(request):
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

        if getattr(user, "last_session_key", None):
            from django.contrib.sessions.models import Session
            try:
                Session.objects.get(session_key=user.last_session_key).delete()
            except Session.DoesNotExist:
                pass

        login(request, user)
        user.last_session_key = request.session.session_key
        user.save(update_fields=["last_session_key"])

        allowed_ids = list(user.companies.values_list("id", flat=True))
        current_id = getattr(user, "company_id", None)
        if current_id not in allowed_ids:
            current_id = allowed_ids[0] if allowed_ids else None

        request.session["active_company_ids"] = [current_id] if current_id else []
        request.session["current_company_id"] = current_id

        next_url = request.GET.get("next") or request.POST.get("next")
        return redirect(next_url or "base:home")
    return render(request, "base/users/login.html", {"form": form})


def logout_view(request):
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
    return render(request, "base/users/profile_page.html")


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
        update_session_auth_hash(request, user)
        messages.success(request, "Your password has been changed successfully.")
        return redirect("base:password_change_done")
    return render(request, "base/users/password_change.html", {"form": form})


@login_required
def password_change_done_view(request):
    return render(request, "base/users/password_change_done.html")




# ------------------------------------------------------------
# Users policy knobs (Odoo-like)
# ------------------------------------------------------------
# هل نسمح بإسناد User إلى شركات غير نشطة من الواجهة؟
USER_ALLOW_ASSIGN_INACTIVE_COMPANIES = False

# هل نُظهر الشركات غير النشطة في فلتر "Company" داخل قائمة المستخدمين؟
USER_LIST_FILTER_SHOW_INACTIVE_COMPANIES = True


def _allowed_company_ids_for_request(request):
    """
    Allowed companies (membership) for admin-like directory views.
    - Superuser: all
    - Normal user: request.user.companies
    """
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return []

    if user.is_superuser:
        return list(Company.objects.values_list("id", flat=True))

    return list(user.companies.values_list("id", flat=True))



# ------------------------------------------------------------
# Dashboard (Odoo-grade, Hybrid UI, company-checkbox scope)
# ------------------------------------------------------------



@dataclass(frozen=True)
class DashboardSearchResult:
    title: str
    subtitle: str
    open_url: str


class HomeView(LoginRequiredMixin, TemplateView):
    """
    Dashboard rules (FINAL):
    - Scope = companies SELECTED by user in Navbar (checkboxes) WITHIN allowed scope.
      Sources:
        * allowed: request.allowed_company_ids (security scope) OR request.user.company_ids
        * selected: request.selected_company_ids (Navbar choice) OR fallback to allowed
      Always: selected ∩ allowed

    - Global search:
      * Single input
      * Top N results per entity
      * “View all results” links to list pages with ?q=...

    - KPIs + Health:
      Practical data quality checks requiring action.

    - Performance:
      Expected < 10k records -> OK on-demand with efficient queries.
    """

    template_name = "home.html"

    RECENT_LIMIT = 6
    SEARCH_LIMIT = 7

    # ---------------------------------------------------------
    # Safe helpers
    # ---------------------------------------------------------
    @staticmethod
    def _has_field(model, field_name: str) -> bool:
        return any(getattr(f, "name", None) == field_name for f in model._meta.get_fields())

    def _filter_active_if_supported(self, qs):
        """
        Applies active=True if the model has 'active' field.
        This keeps behavior consistent across models.
        """
        if self._has_field(qs.model, "active"):
            return qs.filter(active=True)
        return qs

    def _safe_reverse(
        self,
        name: str,
        fallback: str = "#",
        kwargs: dict | None = None,
        query: dict | None = None,
    ) -> str:
        try:
            url = reverse(name, kwargs=kwargs or {})
        except NoReverseMatch:
            return fallback

        if query:
            parts = []
            for k, v in query.items():
                if v is None or v == "":
                    continue
                parts.append(f"{k}={v}")
            if parts:
                url = url + ("&" if "?" in url else "?") + "&".join(parts)
        return url

    # ---------------------------------------------------------
    # Company scope (selected in Navbar within allowed)
    # ---------------------------------------------------------
    def _get_allowed_company_ids(self, Company) -> list[int]:
        """
        Allowed scope (security).
        Prefer middleware injection; fallback to user.company_ids; last resort: any one company.
        """
        allowed = getattr(self.request, "allowed_company_ids", None)
        if allowed:
            try:
                allowed_ids = [int(x) for x in list(allowed)]
            except Exception:
                allowed_ids = []

            if allowed_ids:
                return allowed_ids

        user_allowed = list(getattr(self.request.user, "company_ids", []) or [])
        if user_allowed:
            return [int(x) for x in user_allowed if str(x).isdigit() or isinstance(x, int)]

        # Last resort: avoid crashing dashboard
        return list(Company.objects.values_list("id", flat=True)[:1])

    def _get_selected_company_ids(self, Company, allowed_company_ids: list[int]) -> list[int]:
        """
        Selected scope (user choice) within allowed.
        Primary: request.selected_company_ids (from middleware reading session)
        Fallback: allowed_company_ids
        Always: selected ∩ allowed
        Also enforces Company.active=True if supported.
        """
        selected = getattr(self.request, "selected_company_ids", None)

        if selected:
            try:
                selected_ids = [int(x) for x in list(selected)]
            except Exception:
                selected_ids = list(allowed_company_ids)
        else:
            selected_ids = list(allowed_company_ids)

        # hard safety: intersect with allowed
        allowed_set = set(int(x) for x in allowed_company_ids)
        selected_ids = [cid for cid in selected_ids if int(cid) in allowed_set]

        if not selected_ids:
            selected_ids = list(allowed_company_ids)

        # keep only active companies if Company has 'active'
        qs = Company.objects.filter(id__in=selected_ids)
        qs = self._filter_active_if_supported(qs)

        return list(qs.values_list("id", flat=True))

    # ---------------------------------------------------------
    # Main context
    # ---------------------------------------------------------
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        # Models
        Company = apps.get_model("base", "Company")
        Partner = apps.get_model("base", "Partner")
        User = apps.get_model("base", "User")
        Employee = apps.get_model("hr", "Employee")
        Asset = apps.get_model("assets", "Asset")
        Skill = apps.get_model("skills", "Skill")
        EmployeeSkill = apps.get_model("skills", "EmployeeSkill")
        Payslip = apps.get_model("payroll", "Payslip")

        # -----------------------------------------------------
        # Allowed + Selected company ids
        # -----------------------------------------------------
        allowed_company_ids = self._get_allowed_company_ids(Company)
        selected_company_ids = self._get_selected_company_ids(Company, allowed_company_ids)

        selected_companies_qs = Company.objects.filter(id__in=selected_company_ids).order_by("name")
        selected_companies_qs = self._filter_active_if_supported(selected_companies_qs)

        # Current company badge (optional)
        current_company = None
        current_cid = getattr(self.request, "company_id", None)
        if current_cid:
            current_company = Company.objects.filter(id=current_cid).first()

        # -----------------------------------------------------
        # Scoped querysets (ALL must use selected_company_ids)
        # -----------------------------------------------------
        partners_qs = Partner.objects.filter(company_id__in=selected_company_ids)
        partners_qs = self._filter_active_if_supported(partners_qs)

        # Users: include FK company + M2M companies, scoped to selected
        users_qs = (
            User.objects
            .filter(
                Q(company_id__in=selected_company_ids) |
                Q(companies__id__in=selected_company_ids)
            )
            .distinct()
        )
        # NOTE: لا نُطبق is_active هنا حتى KPI users يعكس جميع المستخدمين داخل scope
        # مؤشرات الصحة ستعالج inactive/unverified وغيرها.

        employees_qs = Employee.objects.filter(company_id__in=selected_company_ids)
        employees_qs = self._filter_active_if_supported(employees_qs)

        assets_qs = Asset.objects.filter(company_id__in=selected_company_ids)
        assets_qs = self._filter_active_if_supported(assets_qs)

        # Skills are global reference data (لا ترتبط بالشركات)
        skills_qs = Skill.objects.all()
        skills_qs = self._filter_active_if_supported(skills_qs)

        employee_skills_qs = EmployeeSkill.objects.filter(company_id__in=selected_company_ids)
        employee_skills_qs = self._filter_active_if_supported(employee_skills_qs)

        payslips_qs = Payslip.objects.filter(company_id__in=selected_company_ids)
        # Payslip غالباً لا يحتوي active

        # -----------------------------------------------------
        # Core KPIs (now fully scoped)
        # -----------------------------------------------------
        kpis = {
            "companies": selected_companies_qs.count(),
            "partners": partners_qs.count(),
            "users": users_qs.count(),
            "employees": employees_qs.count(),
            "assets": assets_qs.count(),
            "skills": skills_qs.count(),  # global by design
            "employee_skills": employee_skills_qs.count(),
            "payslips": payslips_qs.count(),
        }

        # -----------------------------------------------------
        # Breakdowns (scoped)
        # -----------------------------------------------------
        assets_by_status_map = {
            row["status"]: row["cnt"]
            for row in (
                assets_qs.values("status")
                .annotate(cnt=Count("id"))
                .order_by("-cnt")
            )
        }

        payslips_by_state_map = {
            row["state"]: row["cnt"]
            for row in (
                payslips_qs.values("state")
                .annotate(cnt=Count("id"))
                .order_by("-cnt")
            )
        }

        # -----------------------------------------------------
        # Health Indicators (scoped)
        # -----------------------------------------------------
        health = {}

        # Employees without department
        if self._has_field(Employee, "department"):
            health["employees_without_department"] = employees_qs.filter(department__isnull=True).count()
        else:
            health["employees_without_department"] = 0

        # Assets without holder
        if self._has_field(Asset, "holder"):
            health["assets_unassigned"] = assets_qs.filter(holder__isnull=True).count()
        else:
            health["assets_unassigned"] = 0

        # Partners missing contact info (email+phone+mobile)
        # (نقيس "missing all" بشكل صحيح)
        missing_parts = [Q(email="") | Q(email__isnull=True)]
        if self._has_field(Partner, "phone"):
            missing_parts.append(Q(phone="") | Q(phone__isnull=True))
        if self._has_field(Partner, "mobile"):
            missing_parts.append(Q(mobile="") | Q(mobile__isnull=True))

        partner_missing_q = missing_parts[0]
        for extra in missing_parts[1:]:
            partner_missing_q &= extra

        health["partners_missing_contact"] = partners_qs.filter(partner_missing_q).count()

        # Users without partner
        if self._has_field(User, "partner"):
            health["users_without_partner"] = users_qs.filter(partner__isnull=True).count()
        else:
            health["users_without_partner"] = 0

        # Users inactive
        if self._has_field(User, "is_active"):
            health["users_inactive"] = users_qs.filter(is_active=False).count()
        else:
            health["users_inactive"] = 0

        # Users email not verified
        if self._has_field(User, "email_verified"):
            health["users_unverified_email"] = users_qs.filter(email_verified=False).count()
        else:
            health["users_unverified_email"] = 0

        # Payslips unpaid
        if self._has_field(Payslip, "state"):
            health["payslips_unpaid"] = payslips_qs.exclude(state="paid").count()
        else:
            health["payslips_unpaid"] = 0

        # Employees without skills
        if self._has_field(EmployeeSkill, "employee"):
            employee_ids_with_skills = employee_skills_qs.values_list("employee_id", flat=True).distinct()
            health["employees_without_skills"] = employees_qs.exclude(id__in=employee_ids_with_skills).count()
        else:
            health["employees_without_skills"] = 0

        # -----------------------------------------------------
        # Recent activity (scoped)
        # -----------------------------------------------------
        def _attach_open_url(items, url_name: str):
            for obj in items:
                obj.open_url = self._safe_reverse(url_name, kwargs={"pk": obj.pk})
            return items

        recent = {
            "employees": _attach_open_url(
                list(
                    employees_qs.select_related("company", "department", "job")
                    .order_by("-id")[: self.RECENT_LIMIT]
                ),
                "hr:employee_edit",
            ),
            "assets": _attach_open_url(
                list(
                    assets_qs.select_related("company", "category", "department", "holder")
                    .order_by("-id")[: self.RECENT_LIMIT]
                ),
                "assets:asset_edit",
            ),
            "partners": _attach_open_url(
                list(
                    partners_qs.select_related("company", "parent")
                    .order_by("-id")[: self.RECENT_LIMIT]
                ),
                "base:partner_edit",
            ),
            "users": _attach_open_url(
                list(
                    users_qs.select_related("company", "partner")
                    .order_by("-id")[: self.RECENT_LIMIT]
                ),
                "base:user_edit",
            ),
            "payslips": _attach_open_url(
                list(
                    payslips_qs.select_related("company", "employee", "period")
                    .order_by("-id")[: self.RECENT_LIMIT]
                ),
                "payroll:payslip_edit",
            ),
        }

        # -----------------------------------------------------
        # Best-practice global search (scoped)
        # -----------------------------------------------------
        q = (self.request.GET.get("q") or "").strip()
        search = {"q": q, "partners": [], "employees": [], "assets": [], "users": []}

        if q:
            # Partners
            partner_filter = Q(name__icontains=q)
            if self._has_field(Partner, "display_name"):
                partner_filter |= Q(display_name__icontains=q)
            if self._has_field(Partner, "email"):
                partner_filter |= Q(email__icontains=q)
            if self._has_field(Partner, "phone"):
                partner_filter |= Q(phone__icontains=q)
            if self._has_field(Partner, "mobile"):
                partner_filter |= Q(mobile__icontains=q)

            partners_found = (
                partners_qs.filter(partner_filter)
                .select_related("company")
                .order_by("name")[: self.SEARCH_LIMIT]
            )
            search["partners"] = [
                DashboardSearchResult(
                    title=(getattr(p, "display_name", "") or p.name or "—"),
                    subtitle=(str(getattr(p, "company", "")) or ""),
                    open_url=self._safe_reverse("base:partner_detail", kwargs={"pk": p.pk}),
                )
                for p in partners_found
            ]

            # Employees
            emp_filter = Q(name__icontains=q)
            if self._has_field(Employee, "private_phone"):
                emp_filter |= Q(private_phone__icontains=q)
            if self._has_field(Employee, "private_email"):
                emp_filter |= Q(private_email__icontains=q)

            employees_found = (
                employees_qs.filter(emp_filter)
                .select_related("company", "department")
                .order_by("name")[: self.SEARCH_LIMIT]
            )
            search["employees"] = [
                DashboardSearchResult(
                    title=(getattr(e, "name", "") or "—"),
                    subtitle=(str(getattr(e, "department", "")) or ""),
                    open_url=self._safe_reverse("hr:employee_detail", kwargs={"pk": e.pk}),
                )
                for e in employees_found
            ]

            # Assets
            asset_filter = Q(name__icontains=q) | Q(code__icontains=q)
            if self._has_field(Asset, "serial"):
                asset_filter |= Q(serial__icontains=q)

            assets_found = (
                assets_qs.filter(asset_filter)
                .select_related("company")
                .order_by("code")[: self.SEARCH_LIMIT]
            )
            search["assets"] = [
                DashboardSearchResult(
                    title=f"{getattr(a, 'code', '')} — {getattr(a, 'name', '')}".strip(" —"),
                    subtitle=(str(getattr(a, "company", "")) or ""),
                    open_url=self._safe_reverse("assets:asset_detail", kwargs={"pk": a.pk}),
                )
                for a in assets_found
            ]

            # Users
            user_filter = Q(email__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q)
            if self._has_field(User, "partner"):
                user_filter |= Q(partner__name__icontains=q)

            users_found = (
                users_qs.filter(user_filter)
                .select_related("company", "partner")
                .order_by("email")[: self.SEARCH_LIMIT]
            )
            search["users"] = [
                DashboardSearchResult(
                    title=(getattr(u, "email", "") or "—"),
                    subtitle=(u.get_full_name() or (getattr(u, "partner", None) and u.partner.name) or ""),
                    open_url=self._safe_reverse("base:user_detail", kwargs={"pk": u.pk}),
                )
                for u in users_found
            ]

        # -----------------------------------------------------
        # URLs + view-all search links
        # -----------------------------------------------------
        urls = {
            "partners_list": self._safe_reverse("base:partner_list"),
            "partners_create": self._safe_reverse("base:partner_create"),
            "users_list": self._safe_reverse("base:user_list"),
            "users_create": self._safe_reverse("base:user_create"),
            "employees_list": self._safe_reverse("hr:employee_list"),
            "employees_create": self._safe_reverse("hr:employee_create"),
            "assets_list": self._safe_reverse("assets:asset_list"),
            "assets_create": self._safe_reverse("assets:asset_create"),
            "payslips_list": self._safe_reverse("payroll:payslip_list"),
            "payslips_create": self._safe_reverse("payroll:payslip_create"),
        }

        search_all = {
            "partners": self._safe_reverse("base:partner_list", query={"q": q}),
            "employees": self._safe_reverse("hr:employee_list", query={"q": q}),
            "assets": self._safe_reverse("assets:asset_list", query={"q": q}),
            "users": self._safe_reverse("base:user_list", query={"q": q}),
        }

        # -----------------------------------------------------
        # Context
        # -----------------------------------------------------
        ctx.update({
            "current_company": current_company,
            "selected_company_ids": selected_company_ids,
            "selected_companies": selected_companies_qs,

            "kpis": kpis,
            "assets_by_status": assets_by_status_map,
            "payslips_by_state": payslips_by_state_map,
            "health": health,
            "recent": recent,
            "search": search,
            "search_all": search_all,
            "urls": urls,
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



class CompanyScopeMixin:
    """
    يطبّق Company scope (Multi-company) فقط — بدون ACL.
    """

    company_field_name = "company"

    def _active_company_ids(self):
        return get_allowed_company_ids(self.request)

    def _enforce_company_on_queryset(self, qs):
        active_ids = self._active_company_ids()
        if not active_ids:
            return qs.none()

        if qs.model._meta.app_label == "base" and qs.model._meta.model_name == "company":
            return qs.filter(id__in=active_ids)

        if any(f.name == self.company_field_name for f in qs.model._meta.fields):
            return qs.filter(**{f"{self.company_field_name}__in": active_ids})

        return qs

    def _enforce_object_scope_or_404(self, obj):
        active_ids = self._active_company_ids()
        if hasattr(obj, f"{self.company_field_name}_id"):
            cid = getattr(obj, f"{self.company_field_name}_id", None)
            if active_ids and cid not in active_ids:
                raise Http404("Not found")
        return obj

    def _filter_form_related_fields_by_company(self, form):
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

            if any(f.name == self.company_field_name for f in model._meta.fields):
                field.queryset = qs.filter(**{f"{self.company_field_name}__in": active_ids})

    def _set_default_company_on_create(self, form):
        if hasattr(form.instance, f"{self.company_field_name}_id"):
            if not getattr(form.instance, f"{self.company_field_name}_id", None):
                cid = get_company_id(self.request)
                if cid:
                    setattr(form.instance, f"{self.company_field_name}_id", cid)





class BaseScopedListView(CompanyScopeMixin, ListView):

    def get_queryset(self):
        qs = super().get_queryset()
        qs = self._enforce_company_on_queryset(qs)
        return qs


class BaseScopedDetailView(CompanyScopeMixin, DetailView):

    def get_queryset(self):
        qs = super().get_queryset()
        qs = self._enforce_company_on_queryset(qs)
        return qs

    def get_object(self, queryset=None):
        obj = super().get_object(queryset=queryset)
        return self._enforce_object_scope_or_404(obj)


class BaseScopedCreateView(CompanyScopeMixin, CreateView):

    def get_queryset(self):
        qs = super().get_queryset()
        qs = self._enforce_company_on_queryset(qs)
        return qs

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        self._filter_form_related_fields_by_company(form)
        return form

    def form_valid(self, form):
        # ضبط الشركة الافتراضية عند الإنشاء
        self._set_default_company_on_create(form)

        # تأكيد أن الشركة ضمن النطاق النشط
        if hasattr(form.instance, self.company_field_name):
            comp_id = getattr(form.instance, self.company_field_name + "_id", None)
            if comp_id and comp_id not in self._active_company_ids():
                raise Http404("Company is outside active scope.")

        return super().form_valid(form)


class BaseScopedUpdateView(CompanyScopeMixin, UpdateView):

    def get_queryset(self):
        qs = super().get_queryset()
        qs = self._enforce_company_on_queryset(qs)
        return qs

    def get_object(self, queryset=None):
        obj = super().get_object(queryset=queryset)
        return self._enforce_object_scope_or_404(obj)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        self._filter_form_related_fields_by_company(form)
        return form

    def form_valid(self, form):
        # تأكيد أن الشركة بقيت ضمن النطاق النشط
        if hasattr(form.instance, self.company_field_name):
            comp_id = getattr(form.instance, self.company_field_name + "_id", None)
            if comp_id and comp_id not in self._active_company_ids():
                raise Http404("Company is outside active scope.")

        return super().form_valid(form)


class BaseScopedDeleteView(CompanyScopeMixin, DeleteView):
    """
    DeleteView مقيّد فقط بنطاق الشركة (Company Scope)
    بدون أي ACL أو صلاحيات مخصصة.
    """

    def get_queryset(self):
        qs = super().get_queryset()
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


# ------- partner views ---------


class PartnerListView(LoginRequiredMixin, ListView):
    """
    Partner Directory View (Enterprise-grade)

    Rules:
    - Scoped by allowed companies (directory, not active-context)
    - Supports full filtering via PartnerFilterForm
    """

    model = Partner
    paginate_by = 24
    template_name = "base/partner_list.html"

    ORDERING_MAP = {
        "name": "name",
        "latest": "-id",
        "company": "company__name",
    }

    # --------------------------------------------------
    # Base queryset
    # --------------------------------------------------
    def _base_queryset(self):
        return (
            Partner.objects
            .select_related("company", "parent")
            .prefetch_related("categories")
        )

    # --------------------------------------------------
    # Main queryset
    # --------------------------------------------------
    def get_queryset(self):
        qs = self._base_queryset()

        # ------------------------------
        # Company scope
        # ------------------------------
        if not self.request.user.is_superuser:
            allowed_ids = _allowed_company_ids_for_request(self.request)
            qs = qs.filter(
                Q(company_id__in=allowed_ids) |
                Q(parent_company_id__in=allowed_ids)
            ).distinct()

        # ------------------------------
        # Filters
        # ------------------------------
        self.filter_form = self.get_filter_form()

        if self.filter_form.is_valid():
            data = self.filter_form.cleaned_data

            # Search
            q = data.get("q")
            if q:
                qs = qs.filter(
                    Q(name__icontains=q) |
                    Q(display_name__icontains=q) |
                    Q(email__icontains=q) |
                    Q(phone__icontains=q) |
                    Q(mobile__icontains=q)
                )

            # Company
            if data.get("company"):
                qs = qs.filter(company=data["company"])

            # Company type
            if data.get("company_type"):
                qs = qs.filter(company_type=data["company_type"])

            # Contact type
            if data.get("type"):
                qs = qs.filter(type=data["type"])

            # Active
            if data.get("active") == "1":
                qs = qs.filter(active=True)
            elif data.get("active") == "0":
                qs = qs.filter(active=False)

            # Employee
            if data.get("employee") == "1":
                qs = qs.filter(employee=True)
            elif data.get("employee") == "0":
                qs = qs.filter(employee=False)

            # Ordering
            order_key = data.get("order") or "name"
            qs = qs.order_by(self.ORDERING_MAP.get(order_key, "name"))

        return qs

    # --------------------------------------------------
    # Filter form
    # --------------------------------------------------
    def get_filter_form(self):
        if hasattr(self, "filter_form"):
            return self.filter_form

        if self.request.user.is_superuser:
            companies_qs = Company.objects.all()
        else:
            companies_qs = Company.objects.filter(
                id__in=_allowed_company_ids_for_request(self.request)
            )

        return PartnerFilterForm(
            self.request.GET or None,
            allowed_companies=companies_qs.order_by("name")
        )

    # --------------------------------------------------
    # Context
    # --------------------------------------------------
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        ctx["list_model"] = "partner"
        ctx["can_add_partner"] = True
        ctx["partner_change_ids"] = {obj.id for obj in self.object_list}

        ctx["filter_form"] = self.get_filter_form()

        ctx["search_config"] = {
            "placeholder": "Search partners…",
            "show_company_filter": True,
            "show_active_filter": True,
            "show_range_filter": False,
        }

        return ctx


class PartnerCreateView(LoginRequiredMixin, BaseScopedCreateView):
    model = Partner
    form_class = PartnerForm
    template_name = "base/partner_form.html"
    success_url = reverse_lazy("base:partner_list")


class PartnerUpdateView(LoginRequiredMixin, BaseScopedUpdateView):
    """
    Partner Update View (Identity & Contact only)
    """

    model = Partner
    form_class = PartnerForm
    template_name = "base/partner_form.html"
    success_url = reverse_lazy("base:partner_list")

    def get_queryset(self):
        qs = Partner.objects.select_related("company", "parent")
        return self._enforce_company_on_queryset(qs)


class PartnerDetailView(LoginRequiredMixin, BaseScopedDetailView):
    """
    Partner Detail View (Scoped)
    - Read-only directory view
    - Enforces active company scope (multi-company)
    """

    model = Partner
    template_name = "base/partner_detail.html"

    def get_queryset(self):
        qs = Partner.objects.select_related("company", "parent")
        return self._enforce_company_on_queryset(qs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_edit_object"] = True
        return ctx



# ============================================================
# Users (Odoo-like, company-scope aware)
# ============================================================


class UserListView(LoginRequiredMixin, ListView):
    model = User
    template_name = "base/user_list.html"
    paginate_by = 24

    ORDERING_MAP = {
        "email": "email",
        "name": "first_name",
        "company": "company__name",
        "latest": "-id",
    }

    def get_queryset(self):
        qs = (
            User.objects
            .select_related("company", "partner")
            .prefetch_related("companies")
        )

        # -------------------------------------------------
        # Company scope (directory logic, not active context)
        # -------------------------------------------------
        if not self.request.user.is_superuser:
            allowed_ids = self.request.user.company_ids
            qs = qs.filter(
                Q(company_id__in=allowed_ids) |
                Q(companies__id__in=allowed_ids)
            ).distinct()

        # -------------------------------------------------
        # Apply filters via form (FIXED)
        # -------------------------------------------------
        self.filter_form = UserFilterForm(self.request.GET or None)

        # IMPORTANT: inject company queryset BEFORE validation
        if self.request.user.is_superuser:
            companies_qs = Company.objects.all()
        else:
            companies_qs = Company.objects.filter(
                id__in=self.request.user.company_ids
            )

        self.filter_form.set_company_queryset(companies_qs)

        if self.filter_form.is_valid():
            f = self.filter_form.cleaned_data

            # Search
            q = f.get("q")
            if q:
                qs = qs.filter(
                    Q(email__icontains=q) |
                    Q(first_name__icontains=q) |
                    Q(last_name__icontains=q) |
                    Q(partner__name__icontains=q)
                ).distinct()

            # Company
            if f.get("company"):
                c = f["company"]
                qs = qs.filter(
                    Q(company=c) |
                    Q(companies=c)
                ).distinct()

            # Status
            if f.get("is_active") is not None:
                qs = qs.filter(is_active=f["is_active"])

            if f.get("email_verified") is not None:
                qs = qs.filter(email_verified=f["email_verified"])

            if f.get("is_staff") is not None:
                qs = qs.filter(is_staff=f["is_staff"])

            if f.get("is_superuser") is not None:
                qs = qs.filter(is_superuser=f["is_superuser"])

            # Ordering
            order_key = f.get("order") or "email"
            qs = qs.order_by(self.ORDERING_MAP.get(order_key, "email"))

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        # Inject filter form
        form = getattr(self, "filter_form", UserFilterForm())

        ctx["filter_form"] = form
        ctx["can_add_user"] = True
        ctx["user_change_ids"] = {u.id for u in ctx["object_list"]}

        return ctx


class UserDetailView(LoginRequiredMixin, DetailView):
    """
    User Detail View (Company-scope aware, directory)

    Rule:
    - Superuser: allowed
    - Normal user: user must be in allowed scope by:
      (user.company in allowed) OR (user.companies intersects allowed)
    """

    model = User
    template_name = "base/user_detail.html"

    def get_queryset(self):
        return User.objects.select_related("company", "partner").prefetch_related("companies")

    def get_object(self, queryset=None):
        obj = super().get_object(queryset=queryset)

        if self.request.user.is_superuser:
            return obj

        allowed_ids = set(_allowed_company_ids_for_request(self.request))

        in_fk = getattr(obj, "company_id", None) in allowed_ids
        in_m2m = obj.companies.filter(id__in=allowed_ids).exists() if hasattr(obj, "companies") else False

        if not (in_fk or in_m2m):
            raise PermissionDenied("You do not have access to this user.")

        return obj

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_edit_object"] = True
        return ctx


class UserUpdateView(LoginRequiredMixin, UpdateView):
    """
    User Update View (Company-scope aware)

    Rules:
    - Superuser: can edit any user
    - Normal user: can edit only users in allowed scope
    - company / companies fields are restricted to allowed companies
      (and optionally active-only depending on policy)
    """

    model = User
    form_class = UserForm
    template_name = "base/user_form.html"
    success_url = reverse_lazy("base:user_list")

    def get_queryset(self):
        qs = User.objects.select_related("company", "partner").prefetch_related("companies")
        if self.request.user.is_superuser:
            return qs

        allowed_ids = _allowed_company_ids_for_request(self.request)
        return qs.filter(Q(company_id__in=allowed_ids) | Q(companies__id__in=allowed_ids)).distinct()

    def get_form(self, form_class=None):
        form = super().get_form(form_class)

        # Restrict FK company and M2M companies choices
        if self.request.user.is_superuser:
            companies_qs = Company.objects.all()
        else:
            companies_qs = Company.objects.filter(id__in=_allowed_company_ids_for_request(self.request))

        if not USER_ALLOW_ASSIGN_INACTIVE_COMPANIES:
            companies_qs = companies_qs.filter(active=True)

        if "company" in form.fields:
            form.fields["company"].queryset = companies_qs.order_by("name")

        if "companies" in form.fields:
            form.fields["companies"].queryset = companies_qs.order_by("name")

        return form

    def form_valid(self, form):
        # Defensive: ensure selected companies are within allowed scope for non-superuser
        if not self.request.user.is_superuser:
            allowed_ids = set(_allowed_company_ids_for_request(self.request))

            fk_company = form.cleaned_data.get("company")
            if fk_company and fk_company.pk not in allowed_ids:
                raise PermissionDenied("Company is outside allowed scope.")

            m2m_companies = form.cleaned_data.get("companies")
            if m2m_companies:
                bad = [c.pk for c in m2m_companies if c.pk not in allowed_ids]
                if bad:
                    raise PermissionDenied("One or more companies are outside allowed scope.")

        return super().form_valid(form)


class UserCreateView(LoginRequiredMixin, CreateView):
    """
    User Create View (Company-scope aware, Odoo-like)

    Rules:
    - Superuser: can create for any company
    - Normal user: can create only within allowed companies
    - Default company is current company context (if exists) but must be allowed
    - company/companies field choices restricted (active-only optional)
    """

    model = User
    form_class = UserCreateForm
    template_name = "base/user_form.html"
    success_url = reverse_lazy("base:user_list")

    def get_form(self, form_class=None):
        form = super().get_form(form_class)

        # Build allowed companies queryset
        if self.request.user.is_superuser:
            companies_qs = Company.objects.all()
        else:
            companies_qs = Company.objects.filter(id__in=_allowed_company_ids_for_request(self.request))

        if not USER_ALLOW_ASSIGN_INACTIVE_COMPANIES:
            companies_qs = companies_qs.filter(active=True)

        companies_qs = companies_qs.order_by("name")

        if "company" in form.fields:
            form.fields["company"].queryset = companies_qs

        if "companies" in form.fields:
            form.fields["companies"].queryset = companies_qs

        return form

    def get_initial(self):
        initial = super().get_initial()

        # Prefill from active company context (nice UX) لكن ضمن allowed
        cid = get_company_id(self.request)

        if cid:
            if self.request.user.is_superuser:
                allowed = True
            else:
                allowed = cid in set(_allowed_company_ids_for_request(self.request))

            if allowed:
                if "company" in self.form_class.base_fields:
                    initial["company"] = cid
                if "companies" in self.form_class.base_fields:
                    initial["companies"] = [cid]

        return initial

    def form_valid(self, form):
        if not self.request.user.is_superuser:
            allowed_ids = set(_allowed_company_ids_for_request(self.request))

            fk_company = form.cleaned_data.get("company")
            if fk_company and fk_company.pk not in allowed_ids:
                raise PermissionDenied("Company is outside allowed scope.")

            m2m_companies = form.cleaned_data.get("companies")
            if m2m_companies:
                bad = [c.pk for c in m2m_companies if c.pk not in allowed_ids]
                if bad:
                    raise PermissionDenied("One or more companies are outside allowed scope.")

        return super().form_valid(form)



# --- Companies ---
class CompanyListView(LoginRequiredMixin, BaseScopedListView):
    """
    Company List View (Enterprise-grade)

    Features:
    - Company scope (multi-company)
    - Search by name
    - Active / inactive filter
    - Parent company filter
    - Controlled ordering
    - Pagination
    """

    model = Company
    template_name = "base/company_list.html"
    paginate_by = 24

    # -----------------------------------
    # Ordering whitelist (UI → DB)
    # -----------------------------------
    ORDERING_MAP = {
        "name": "name",
        "latest": "-id",
        "active": ("-active", "name"),
    }

    def get_queryset(self):
        qs = Company.objects.all()

        if not self.request.user.is_superuser:
            allowed_ids = self.request.user.companies.values_list("id", flat=True)
            qs = qs.filter(id__in=allowed_ids)

        # -----------------------------------
        # Parent company filter (hierarchy-aware)
        # -----------------------------------
        parent_id = self.request.GET.get("parent")
        if parent_id:
            try:
                parent = Company.objects.get(pk=int(parent_id))

                # Include selected parent + all its descendants
                qs = qs.filter(
                    parent_path__startswith=parent.parent_path
                )

            except (Company.DoesNotExist, ValueError, TypeError):
                pass

        qs = apply_search_filters(
            self.request,
            qs,
            search_fields=["name"],
        )

        # -----------------------------------
        # Active / Inactive filter
        # -----------------------------------
        active = self.request.GET.get("active")
        if active in ("0", "1"):
            qs = qs.filter(active=(active == "1"))

        order_key = self.request.GET.get("order") or "name"
        ordering = self.ORDERING_MAP.get(order_key)
        if ordering:
            qs = qs.order_by(*ordering) if isinstance(ordering, (list, tuple)) else qs.order_by(ordering)

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        ctx["list_model"] = self.model._meta.model_name
        ctx["can_add_company"] = True

        ctx["company_change_ids"] = {obj.id for obj in self.object_list}

        # Parent companies for filter dropdown
        allowed_ids = get_allowed_company_ids(self.request)

        parent_qs = Company.objects.filter(active=True)

        # تطبيق Company Scope
        if allowed_ids:
            parent_qs = parent_qs.filter(id__in=allowed_ids)

        # ترتيب هرمي صحيح (يعتمد على parent_path)
        ctx["parent_companies"] = parent_qs.order_by("parent_path", "name")

        # 🔍 Search panel configuration (بديل with)
        ctx["search_config"] = {
            "placeholder": "Search company name…",
            "show_company_filter": False,
            "show_active_filter": True,
            "show_range_filter": False,
        }

        ctx["filters"] = {
            "q": self.request.GET.get("q", ""),
            "active": self.request.GET.get("active", ""),
            "parent": self.request.GET.get("parent", ""),
            "order": self.request.GET.get("order", ""),
        }

        return ctx


class CompanyDetailView(LoginRequiredMixin, DetailView):
    """
    Company Detail View (Company-scope aware)

    Rules:
    - Enforces company scope
    - Allows access only to allowed companies
    - Superuser bypass supported
    """

    model = Company
    template_name = "base/company_detail.html"

    def get_object(self, queryset=None):
        """
        Enforce Company Scope explicitly.
        Prevent access to companies outside allowed scope.
        """
        obj = super().get_object(queryset=queryset)

        # Superuser can access everything
        if self.request.user.is_superuser:
            return obj

        # Allowed companies = user.companies (NOT active context)
        allowed_ids = self.request.user.companies.values_list("id", flat=True)

        if obj.pk not in allowed_ids:
            raise PermissionDenied("You do not have access to this company.")

        return obj

    def get_queryset(self):
        """
        Optimize related objects loading only.
        Scope enforced in get_object().
        """
        return (
            Company.objects
            .select_related("parent", "partner")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        company = self.object
        partner = company.partner

        # ----------------------------------
        # Permissions / actions
        # ----------------------------------
        ctx["can_edit_object"] = True

        # ----------------------------------
        # Identity data (read-only, from Partner)
        # ----------------------------------
        ctx["company_identity"] = {
            "email": company.email,
            "phone": company.phone,
            "website": company.website,
            "vat": company.vat,
            "company_registry": company.company_registry,
        }

        ctx["company_address"] = {
            "street": company.street,
            "street2": company.street2,
            "city": company.city,
            "state": company.state,
            "zip": company.zip,
            "country": company.country,
        }

        # ----------------------------------
        # Hierarchy info
        # ----------------------------------
        ctx["company_parent"] = company.parent
        ctx["company_children"] = company.children.filter(active=True).order_by("name")

        # ----------------------------------
        # Company state
        # ----------------------------------
        ctx["company_state"] = {
            "active": company.active,
            "is_current": (
                hasattr(self.request, "current_company")
                and self.request.current_company
                and self.request.current_company.id == company.id
            ),
        }

        return ctx


class CompanyUpdateView(LoginRequiredMixin, UpdateView):
    """
    Company Update View (Enterprise-grade, Odoo-like)

    Key rules:
    - Company is a structural object
    - NOT restricted by active company context
    - Access controlled by user.companies only
    """

    model = Company
    form_class = CompanyForm
    template_name = "base/company_form.html"
    success_url = reverse_lazy("base:company_list")

    # ------------------------------------------------------------------
    # Object retrieval
    # ------------------------------------------------------------------
    def get_object(self, queryset=None):
        obj = super().get_object(queryset)

        # Superuser bypass
        if self.request.user.is_superuser:
            return obj

        allowed_ids = self.request.user.companies.values_list("id", flat=True)

        if obj.pk not in allowed_ids:
            raise PermissionDenied("You do not have access to this company.")

        return obj

    # ------------------------------------------------------------------
    # Form preparation (restrict parent choices)
    # ------------------------------------------------------------------
    def get_form(self, form_class=None):
        form = super().get_form(form_class)

        allowed_ids = self.request.user.companies.values_list("id", flat=True)

        parent_qs = (
            Company.objects
            .filter(active=True, id__in=allowed_ids)
            .order_by("name")
        )

        # Exclude self from parent options
        if self.object:
            parent_qs = parent_qs.exclude(id=self.object.id)

        form.fields["parent"].queryset = parent_qs

        return form

    # ------------------------------------------------------------------
    # Final validation before save
    # ------------------------------------------------------------------
    def form_valid(self, form):
        allowed_ids = self.request.user.companies.values_list("id", flat=True)

        if form.instance.pk not in allowed_ids:
            raise PermissionDenied("You do not have access to this company.")

        parent = form.cleaned_data.get("parent")
        if parent and parent.pk not in allowed_ids:
            raise PermissionDenied("Parent company is outside allowed scope.")

        return super().form_valid(form)


class CompanyCreateView(LoginRequiredMixin, CreateView):
    """
    Company Create View (Enterprise-grade, Odoo-like)

    Design rules:
    - Company is a structural object
    - Parent company choices:
        - Active companies only
        - Within user's allowed companies
    - No dependency on active company context
    """

    model = Company
    form_class = CompanyForm
    template_name = "base/company_form.html"
    success_url = reverse_lazy("base:company_list")

    # ------------------------------------------------------------------
    # Form preparation (restrict parent choices)
    # ------------------------------------------------------------------
    def get_form(self, form_class=None):
        form = super().get_form(form_class)

        # Superuser: see all active companies
        if self.request.user.is_superuser:
            parent_qs = Company.objects.filter(active=True)
        else:
            allowed_ids = self.request.user.companies.values_list("id", flat=True)
            parent_qs = Company.objects.filter(
                active=True,
                id__in=allowed_ids,
            )

        form.fields["parent"].queryset = parent_qs.order_by("name")

        return form

    # ------------------------------------------------------------------
    # Final validation before save
    # ------------------------------------------------------------------
    def form_valid(self, form):
        # Superuser bypass
        if self.request.user.is_superuser:
            return super().form_valid(form)

        allowed_ids = self.request.user.companies.values_list("id", flat=True)

        parent = form.cleaned_data.get("parent")
        if parent and parent.pk not in allowed_ids:
            raise PermissionDenied("Parent company is outside allowed scope.")

        return super().form_valid(form)

    def get_initial(self):
        initial = super().get_initial()
        initial.setdefault("active", True)
        return initial



# -----------terms_of_service and privacy_policy ------------

class TermsOfServiceView(TemplateView):
    template_name = "pages/terms_of_service.html"


class PrivacyPolicyView(TemplateView):
    template_name = "pages/privacy_policy.html"
