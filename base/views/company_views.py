from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import FormView, TemplateView

from ..forms import CompanySwitchForm

class CompanySwitchView(LoginRequiredMixin, FormView):
    template_name = "base/company_switch.html"
    form_class = CompanySwitchForm
    success_url = reverse_lazy("home")  # يوجّه إلى templates/home.html

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
        # خزّن الكل + شركة افتراضية (الأولى) للعمل
        self.request.session["active_company_ids"] = ids
        self.request.session["current_company_id"] = ids[0] if ids else None
        messages.success(self.request, "Active companies updated.")
        return super().form_valid(form)

# class CompanySwitchedView(LoginRequiredMixin, TemplateView):
#     template_name = "base/company_switched.html"
