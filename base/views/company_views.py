from django.urls import reverse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import FormView, TemplateView

from ..forms import CompanySwitchForm

class CompanySwitchView(LoginRequiredMixin, FormView):
    template_name = "base/company_switch.html"
    form_class = CompanySwitchForm
    success_url = reverse_lazy("base:home")  # يوجّه إلى templates/home.html

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        # مرّر قائمة الشركات المفعّلة حاليًا ليتم اختيارها افتراضيًا
        current_ids = self.request.session.get("active_company_ids")
        if not current_ids:
            default_id = getattr(self.request.user, "company_id", None)
            current_ids = [default_id] if default_id else []
        kwargs["current_ids"] = current_ids
        return kwargs

    def form_valid(self, form):
        companies_qs = form.cleaned_data["companies"]
        ids = list(companies_qs.values_list("id", flat=True))

        # لا توجد شركات مختارة → أعد نفس الصفحة مع رسالة خطأ (Odoo-like guard)
        if not ids:
            form.add_error("companies", "Please select at least one company.")
            from django.contrib import messages
            messages.error(self.request, "You must select at least one company.")
            return self.form_invalid(form)

        # خزّن الكل + شركة نشطة (الأولى)
        self.request.session["active_company_ids"] = ids
        self.request.session["current_company_id"] = ids[0]

        from django.contrib import messages
        messages.success(self.request, "Active companies updated.")
        return super().form_valid(form)

    def get_success_url(self):
        # يدعم next في GET أو POST
        next_url = self.request.GET.get("next") or self.request.POST.get("next")
        return next_url if next_url else reverse("base:home")
