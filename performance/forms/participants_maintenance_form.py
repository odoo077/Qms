# -*- coding: utf-8 -*-
from django import forms

class RebuildParticipantsForm(forms.Form):
    """
    فورم بسيط لتأكيد إجراء إعادة بناء المشاركين لهدف محدد أو مجموعة أهداف.
    يفضّل تنفيذ الفعل في الـ View (خلف POST) داخل معاملة (transaction.atomic).
    """
    confirm = forms.BooleanField(
        required=True,
        label="I confirm rebuilding participants for the selected objective(s)."
    )
