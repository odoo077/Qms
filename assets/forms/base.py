# assets/forms/base.py
from django import forms

class TailwindFormMixin:
    """
    يضيف أصناف Tailwind/DaisyUI المناسبة لكل الحقول تلقائيًا.
    استُخدم نفس الأسلوب في التطبيقات الأخرى (hr/skills) للحفاظ على الاتساق.
    """
    base_input_cls = "input input-bordered w-full"
    base_select_cls = "select select-bordered w-full"
    base_textarea_cls = "textarea textarea-bordered w-full"

    def _style_field(self, name, field):
        w = field.widget
        # Date/DateTime
        if isinstance(w, (forms.DateInput, forms.DateTimeInput)):
            w.attrs.setdefault("class", self.base_input_cls)
            if isinstance(w, forms.DateInput):
                w.input_type = "date"
            else:
                w.input_type = "datetime-local"
            return

        # Textarea
        if isinstance(w, forms.Textarea):
            w.attrs.setdefault("class", self.base_textarea_cls)
            return

        # Select & Radio/Checkbox
        if isinstance(w, (forms.Select, forms.SelectMultiple)):
            w.attrs.setdefault("class", self.base_select_cls)
            return

        if isinstance(w, (forms.CheckboxInput, forms.RadioSelect)):
            # اتركها كما هي
            return

        # Default (text/number/email…)
        w.attrs.setdefault("class", self.base_input_cls)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            self._style_field(name, field)


class CompanyScopedFormMixin:
    """
    يسمح بتمرير الشركة الحالية لتصفية الـ QuerySets.
    تمريرها من الـ View عبر: form = MyForm(company=current_company, ...)
    """
    def __init__(self, *args, **kwargs):
        self.company = kwargs.pop("company", None)
        super().__init__(*args, **kwargs)
