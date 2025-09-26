from django import template

register = template.Library()

def _merged_attrs(field, extra):
    attrs = field.field.widget.attrs.copy()
    # دمج class إن وجد
    if 'class' in extra:
        existing = attrs.get('class', '')
        if existing:
            attrs['class'] = f"{existing} {extra['class']}".strip()
        else:
            attrs['class'] = extra['class']
        extra = {k: v for k, v in extra.items() if k != 'class'}
    attrs.update(extra)
    return attrs

@register.filter
def add_class(field, css_classes: str):
    """إضافة كلاس للعنصر"""
    return field.as_widget(attrs=_merged_attrs(field, {'class': css_classes}))

@register.filter
def attr(field, arg: str):
    """
    تعيين/إضافة خاصية واحدة.
    الاستخدام: {{ field|attr:"placeholder:Email" }} أو {{ field|attr:"autocomplete:username" }}
    """
    if ':' in arg:
        key, value = arg.split(':', 1)
    else:
        key, value = arg, ''
    return field.as_widget(attrs=_merged_attrs(field, {key: value}))
