from django import forms

_TW_INPUT = "input input-bordered w-full"
_TW_SELECT = "select select-bordered w-full"
_TW_TEXTAREA = "textarea textarea-bordered w-full"
_TW_FILE = "file-input file-input-bordered w-full"


class TailwindModelForm(forms.ModelForm):
    """
    قاعدة تنسيق تلقائي (Tailwind/DaisyUI) لكل الحقول.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for _, field in self.fields.items():
            w = field.widget
            if isinstance(w, (forms.TextInput, forms.EmailInput, forms.NumberInput, forms.PasswordInput, forms.DateInput, forms.URLInput)):
                w.attrs.setdefault("class", _TW_INPUT)
                if isinstance(w, forms.DateInput):
                    w.attrs.setdefault("type", "date")
            elif isinstance(w, (forms.Select, forms.SelectMultiple)):
                w.attrs.setdefault("class", _TW_SELECT)
            elif isinstance(w, forms.Textarea):
                w.attrs.setdefault("class", _TW_TEXTAREA)
            elif isinstance(w, forms.FileInput):
                w.attrs.setdefault("class", _TW_FILE)
            else:
                w.attrs.setdefault("class", _TW_INPUT)
