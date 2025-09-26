# base/forms/company_forms.py
from django import forms
from ..models import Company

class CompanySwitchForm(forms.Form):
    """
    يسمح باختيار عدة شركات دفعة واحدة.
    - queryset محصور بشركات المستخدم المسموح بها.
    - يملأ initial بالقائمة الحالية (active_company_ids) إن وُجدت.
    """
    def __init__(self, *args, user=None, current_ids=None, **kwargs):
        super().__init__(*args, **kwargs)
        qs = user.companies.all() if user else Company.objects.none()
        self.fields["companies"] = forms.ModelMultipleChoiceField(
            queryset=qs,
            required=True,
            label="Companies",
            help_text="Select one or more companies to work under.",
            widget=forms.SelectMultiple(attrs={"class": "select select-bordered w-full", "size": 6}),
        )
        if current_ids:
            self.initial["companies"] = qs.filter(id__in=current_ids)
