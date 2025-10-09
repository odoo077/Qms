# assets/views/base.py
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied

class CompanyContextMixin(LoginRequiredMixin):
    """
    يوفّر self.company من request ويمنع الوصول إن لم يكن المستخدم ضمن شركاته المسموح بها.
    يفترض أن middleware/context_processor يضع الشركة الحالية في request.company أو السياق.
    """
    company_context_key = "current_company"

    def dispatch(self, request, *args, **kwargs):
        self.company = getattr(request, "company", None) or getattr(request, self.company_context_key, None)
        if self.company:
            # تحقّق أن المستخدم يملك صلاحية الوصول لهذه الشركة
            user = request.user
            # superuser يسمح دائمًا
            if not user.is_superuser:
                # إن كان للمستخدم علاقة many2many باسم companies
                companies_qs = getattr(user, "companies", None)
                if companies_qs is not None and not companies_qs.filter(pk=self.company.pk).exists():
                    raise PermissionDenied("You are not allowed to access this company.")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["current_company"] = self.company
        return ctx


class SuccessMessageMixin:
    success_message = None

    def form_valid(self, form):
        res = super().form_valid(form)
        if self.success_message:
            messages.success(self.request, self.success_message)
        return res
