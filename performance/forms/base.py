# -*- coding: utf-8 -*-
from django import forms

class TailwindFormMixin:
    """
    يضيف أصناف Tailwind/DaisyUI المناسبة لكل الحقول تلقائيًا
    للحفاظ على اتساق الواجهات بين التطبيقات.
    """
    base_input_cls = "input input-bordered w-full"
    base_select_cls = "select select-bordered w-full"
    base_textarea_cls = "textarea textarea-bordered w-full"

    def _style_field(self, name, field):
        w = field.widget
        # تاريخ/تاريخ-وقت
        if isinstance(w, (forms.DateInput, forms.DateTimeInput)):
            w.attrs.setdefault("class", self.base_input_cls)
            if isinstance(w, forms.DateInput):
                w.input_type = "date"
            else:
                w.input_type = "datetime-local"
            return
        # نص متعدد الأسطر
        if isinstance(w, forms.Textarea):
            w.attrs.setdefault("class", self.base_textarea_cls)
            return
        # سيلكت
        if isinstance(w, (forms.Select, forms.SelectMultiple)):
            w.attrs.setdefault("class", self.base_select_cls)
            return
        # شيك/راديو: نتركها كما هي
        if isinstance(w, (forms.CheckboxInput, forms.RadioSelect)):
            return
        # افتراضي (نص/رقم/إيميل…)
        w.attrs.setdefault("class", self.base_input_cls)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            self._style_field(name, field)


class CompanyScopedFormMixin:
    """
    يسمح بتمرير الشركة الحالية لتصفية الـ QuerySets داخل الفورم.
    - مرّرها من الـ View عبر: MyForm(company=current_company, ...)
    - الهدف: تقليل الخيارات للمستخدم وحماية النطاق (Scope).
    """
    def __init__(self, *args, **kwargs):
        self.company = kwargs.pop("company", None)
        super().__init__(*args, **kwargs)
