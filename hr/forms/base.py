# base.py يحتوي على الكلاس الأساسي TailwindModelForm (لتحسين المظهر عبر DaisyUI).

from django import forms

_TW_INPUT = "input input-bordered w-full"
_TW_SELECT = "select select-bordered w-full"
_TW_TEXTAREA = "textarea textarea-bordered w-full"


class TailwindModelForm(forms.ModelForm):
    """
    قاعدة لإضافة كلاس Tailwind/DaisyUI تلقائيًا لكل الحقول.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, (forms.TextInput, forms.EmailInput, forms.NumberInput, forms.PasswordInput)):
                widget.attrs.setdefault("class", _TW_INPUT)
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                widget.attrs.setdefault("class", _TW_SELECT)
            elif isinstance(widget, forms.Textarea):
                widget.attrs.setdefault("class", _TW_TEXTAREA)
            else:
                widget.attrs.setdefault("class", _TW_INPUT)
