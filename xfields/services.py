from __future__ import annotations

# ============================================================
# xfields/services.py
# طبقة خدمات لقراءة/كتابة/تصفية القيم ديناميكيًا
# ============================================================

from typing import Any, Iterable
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import QuerySet
from .models import XField, XValue

# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def _ct_for(obj_or_model):
    if isinstance(obj_or_model, type):
        return ContentType.objects.get_for_model(obj_or_model)
    return ContentType.objects.get_for_model(obj_or_model.__class__)


def _get_field(ct: ContentType, code: str, company_id: int | None = None) -> XField:
    qs = XField.objects.filter(model=ct, code=code)
    if company_id is not None:
        qs = qs.filter(company_id__in=[company_id, None])
    return qs.order_by("-company_id").first()  # يفضّل حقول الشركة ثم العامة


# ------------------------------------------------------------
# API: set/get
# ------------------------------------------------------------
@transaction.atomic
def set_value(obj, code: str, value, *, user, company_id: int | None = None) -> XValue:
    """
    يكتب قيمة الحقل (ينشئ أو يحدث) بشرط امتلاك المستخدم change على الكائن الهدف.
    """

    ct = _ct_for(obj)
    xf = _get_field(ct, code, company_id)
    if not xf:
        raise ValueError(f"XField not found: {ct.app_label}.{ct.model}:{code}")

    xv, _ = XValue.objects.get_or_create(field=xf, content_type=ct, object_id=obj.pk)
    xv.value = value
    xv.full_clean()
    xv.save()
    return xv



def get_value(obj, code: str, *, user, default=None, company_id: int | None = None):
    """
    يقرأ قيمة الحقل بشرط امتلاك المستخدم view على الكائن الهدف.
    """

    ct = _ct_for(obj)
    xf = _get_field(ct, code, company_id)
    if not xf:
        return default
    try:
        xv = XValue.objects.get(field=xf, content_type=ct, object_id=obj.pk)
        return xv.value
    except XValue.DoesNotExist:
        return default



# ------------------------------------------------------------
# API: filter_by_xfield
# ------------------------------------------------------------
def filter_by_xfield(qs: QuerySet, code: str, value, company_id: int | None = None) -> QuerySet:
    """
    يرشّح QuerySet حسب قيمة حقل ديناميكي.
    يعمل عبر join ضمني (subquery).
    """
    model = qs.model
    ct = ContentType.objects.get_for_model(model)
    xf = _get_field(ct, code, company_id)
    if not xf:
        # لا يوجد تعريف → نُبقي الاستعلام كما هو (بدون ترشيح)
        return qs

    # بناء ترشيح حسب نوع الحقل
    filter_kwargs = {
        "field": xf,
        "content_type": ct,
        "object_id__in": qs.values_list("pk", flat=True),
    }

    if xf.field_type == XField.FIELD_CHAR:
        filter_kwargs["char_value"] = value
    elif xf.field_type == XField.FIELD_TEXT:
        filter_kwargs["text_value__icontains"] = value
    elif xf.field_type == XField.FIELD_INT:
        filter_kwargs["int_value"] = int(value)
    elif xf.field_type == XField.FIELD_FLOAT:
        filter_kwargs["float_value"] = float(value)
    elif xf.field_type == XField.FIELD_BOOL:
        filter_kwargs["bool_value"] = bool(value)
    elif xf.field_type == XField.FIELD_DATE:
        filter_kwargs["date_value"] = value
    elif xf.field_type == XField.FIELD_DATETIME:
        filter_kwargs["datetime_value"] = value
    elif xf.field_type in (XField.FIELD_CHOICE, XField.FIELD_MULTI):
        # القيمة ضمن json_value
        filter_kwargs["json_value__contains"] = [value]
    else:
        filter_kwargs["json_value"] = value

    matched_ids = XValue.objects.filter(**filter_kwargs).values_list("object_id", flat=True)
    return qs.filter(pk__in=matched_ids)
