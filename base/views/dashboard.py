# base/views/dashboard.py
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.apps import apps

class HomeView(LoginRequiredMixin, TemplateView):
    template_name = "home.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        Company = apps.get_model("base", "Company")
        Partner = apps.get_model("base", "Partner")
        User    = apps.get_model("base", "User")

        # الشركة الحالية (إن وُجدت) من السيشن
        current_company = None
        cid = self.request.session.get("current_company_id")
        if cid:
            current_company = Company.objects.filter(id=cid).first()
        ctx["current_company"] = current_company

        # الشركات المسموح بها (عدّلها لاحقًا حسب صلاحياتك إن لزم)
        allowed_companies = Company.objects.all()

        # فلترة الإحصاءات حسب الشركة الحالية إن وجدت
        if current_company:
            partners_qs = Partner.objects.filter(company=current_company)
            users_qs = User.objects.filter(company=current_company) if hasattr(User, "company") else User.objects.all()
        else:
            partners_qs = Partner.objects.all()
            users_qs = User.objects.all()

        ctx.update({
            "companies_count": allowed_companies.count(),
            "partners_count": partners_qs.count(),
            "users_count": users_qs.count(),
            "recent_partners": partners_qs.order_by("-id")[:8],
            "recent_users": users_qs.order_by("-date_joined")[:8] if hasattr(User, "date_joined") else users_qs.order_by("-id")[:8],
            "recent_companies": allowed_companies.order_by("-id")[:9],
        })
        return ctx
