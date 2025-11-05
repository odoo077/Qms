# xfield/models.py

from __future__ import annotations

# ============================================================
# xfields/models.py
# منظومة حقول ديناميكية (Odoo Studio-like) كإضافة مستقلة
# ============================================================

from django.db import models, transaction
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
import json


# ------------------------------------------------------------------
# 1) تعريف الحقل المخصص XField (مرتبط بموديل عبر ContentType)
# ------------------------------------------------------------------
class XField(models.Model):
    """
    تعريف حقل ديناميكي لموديل معيّن.
    - لا ننشئ عمودًا جديدًا في جدول الهدف؛ نخزن القيم في XValue.
    - يدعم أنواعًا شائعة: نص/عدد/منطقي/تاريخ/وقت/اختيارات/متعدد.
    """

    FIELD_CHAR = "char"
    FIELD_TEXT = "text"
    FIELD_INT = "int"
    FIELD_FLOAT = "float"
    FIELD_BOOL = "bool"
    FIELD_DATE = "date"
    FIELD_DATETIME = "datetime"
    FIELD_CHOICE = "choice"        # اختيار مفرد من قائمة
    FIELD_MULTI = "multi_choice"   # اختيار متعدد (قائمة قيم)

    FIELD_TYPES = [
        (FIELD_CHAR, "Char"),
        (FIELD_TEXT, "Text"),
        (FIELD_INT, "Integer"),
        (FIELD_FLOAT, "Float"),
        (FIELD_BOOL, "Boolean"),
        (FIELD_DATE, "Date"),
        (FIELD_DATETIME, "DateTime"),
        (FIELD_CHOICE, "Choice (single)"),
        (FIELD_MULTI, "Multi-Choice"),
    ]

    # الموديل الهدف
    model = models.ForeignKey(ContentType, on_delete=models.CASCADE, related_name="xfields")

    # نطاق شركة اختياري (إن أردت حقولًا خاصة بكل شركة)
    company = models.ForeignKey("base.Company", null=True, blank=True, on_delete=models.CASCADE, related_name="xfields")

    # اسم العرض + الاسم التقني
    name = models.CharField(max_length=255)
    code = models.SlugField(max_length=80)  # مثل: "skill_level", "grade"
    field_type = models.CharField(max_length=20, choices=FIELD_TYPES)

    required = models.BooleanField(default=False)
    # إن كان False → قيمة مفردة لكل سجل
    # إن كان True  → نسمح بقيم متعددة (لكننا عادةً نستخدم FIELD_MULTI لهذا الغرض)
    allow_multiple = models.BooleanField(default=False)

    help_text = models.CharField(max_length=500, blank=True, default="")

    class Meta:
        db_table = "xf_field"
        unique_together = [
            ("model", "company", "code"),
        ]
        indexes = [
            models.Index(fields=["model", "code"]),
            models.Index(fields=["company"]),
        ]

    def __str__(self):
        return f"{self.model.app_label}.{self.model.model}::{self.code}"

    def clean(self):
        super().clean()
        # منع allow_multiple مع أنواع لا تدعم منطقياً التعدد إلا عبر json
        if self.allow_multiple and self.field_type not in {self.FIELD_MULTI, self.FIELD_CHOICE, self.FIELD_CHAR, self.FIELD_INT, self.FIELD_FLOAT}:
            # نسمح بالتعدد لبعض الأنواع من خلال json_value
            pass


# ------------------------------------------------------------------
# 2) خيارات الحقل (للأنواع القائمة على الاختيار)
# ------------------------------------------------------------------
class XFieldOption(models.Model):
    field = models.ForeignKey(XField, on_delete=models.CASCADE, related_name="options")
    value = models.CharField(max_length=255)  # القيمة المخزنة
    label = models.CharField(max_length=255)  # ما يُعرض للمستخدم
    sequence = models.IntegerField(default=10)

    class Meta:
        db_table = "xf_field_option"
        unique_together = [("field", "value")]
        ordering = ["field", "sequence", "id"]
        constraints = [
            models.CheckConstraint(
                name="xf_option_value_not_empty",
                check=~models.Q(value=""),
            ),
        ]

    def __str__(self):
        return f"{self.field.code} :: {self.label} ({self.value})"


# ------------------------------------------------------------------
# 3) قيمة الحقل لكل سجل XValue (Generic)
# ------------------------------------------------------------------
class XValue(models.Model):
    """
    تخزين القيم الفعلية لكل سجل هدف (GenericForeignKey).
    - نخزن جميع الأنواع بأعمدة منفصلة + json للمتعدد.
    - نعرض `value` كخاصية مريحة للقراءة/الكتابة حسب نوع الحقل.
    """

    field = models.ForeignKey(XField, on_delete=models.CASCADE, related_name="values")

    # الهدف (أي موديل)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, related_name="xf_values")
    object_id = models.PositiveBigIntegerField()
    target = GenericForeignKey("content_type", "object_id")

    # تخزين متعدد الأنواع
    char_value = models.CharField(max_length=500, null=True, blank=True)
    text_value = models.TextField(null=True, blank=True)
    int_value = models.BigIntegerField(null=True, blank=True)
    float_value = models.FloatField(null=True, blank=True)
    bool_value = models.BooleanField(null=True, blank=True)
    date_value = models.DateField(null=True, blank=True)
    datetime_value = models.DateTimeField(null=True, blank=True)
    json_value = models.JSONField(null=True, blank=True)  # للتعدد/المصفوفات

    class Meta:
        db_table = "xf_value"
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
            models.Index(fields=["field", "content_type", "object_id"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["field", "content_type", "object_id"],
                name="xf_one_value_per_field_per_record",
            ),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError
        super().clean()

        # إذا لم تُحدد content_type بعد (داخل Inline قبل الحفظ) → تخطّ الفحص
        if not getattr(self, "content_type_id", None):
            return

        # تحقق من required
        if self.field.required:
            if self.field.field_type in (XField.FIELD_MULTI, XField.FIELD_CHOICE):
                if not self.json_value:
                    raise ValidationError({"json_value": _("This field is required.")})
            else:
                if (self.value is None) or (self.value == ""):
                    raise ValidationError({"value": _("This field is required.")})

        # ✅ اتساق الشركة (اختياري مُفعّل): إن كان للـ XField شركة، والهدف لديه company_id
        xf_company = getattr(self.field, "company_id", None)
        # target متاح عادةً عبر GenericForeignKey (يُتوقع وجوده بعد content_type/object_id)
        target_obj = getattr(self, "target", None)
        t_company = getattr(target_obj, "company_id", None)
        if xf_company and t_company and xf_company != t_company:
            raise ValidationError(_("XField company must match target object's company."))

        # تحقق من خيارات الحقول للأنواع choice/multi_choice
        if self.field.field_type in (XField.FIELD_CHOICE, XField.FIELD_MULTI) and self.json_value:
            allowed = set(self.field.options.values_list("value", flat=True))
            picked = set(self.json_value or [])
            illegal = picked - allowed
            if illegal:
                raise ValidationError({"json_value": _(f"Invalid options: {sorted(illegal)}")})

        # السماح بسجل واحد لكل (field, content_type, object_id)
        if self.content_type_id and self.object_id:
            qs = type(self).objects.filter(
                field=self.field,
                content_type=self.content_type,
                object_id=self.object_id,
            )
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError(_("Only one value record is allowed for this field on this object."))

    # --------------------------
    # إدارة القيمة كسمة واحدة
    # --------------------------
    @property
    def value(self):
        t = self.field.field_type
        if t == XField.FIELD_CHAR:
            return self.char_value
        if t == XField.FIELD_TEXT:
            return self.text_value
        if t == XField.FIELD_INT:
            return self.int_value
        if t == XField.FIELD_FLOAT:
            return self.float_value
        if t == XField.FIELD_BOOL:
            return self.bool_value
        if t == XField.FIELD_DATE:
            return self.date_value
        if t == XField.FIELD_DATETIME:
            return self.datetime_value
        if t in (XField.FIELD_CHOICE, XField.FIELD_MULTI):
            return self.json_value
        return self.json_value


    def short_value(self) -> str:
        """
        عرض مختصر للقيمة — مفيد للأدمن (يتعامل مع النص/العدد/القائمة/JSON).
        """
        v = self.value
        if isinstance(v, (list, dict)):
            import json as _json
            s = _json.dumps(v, ensure_ascii=False)
        else:
            s = "" if v is None else str(v)
        return (s[:100] + "…") if len(s) > 100 else s


    @value.setter
    def value(self, v):
        t = self.field.field_type
        # تنظيف جميع الحقول قبل التعيين
        self.char_value = self.text_value = None
        self.int_value = self.float_value = None
        self.bool_value = None
        self.date_value = self.datetime_value = None
        self.json_value = None

        if t == XField.FIELD_CHAR:
            self.char_value = None if v is None else str(v)
        elif t == XField.FIELD_TEXT:
            self.text_value = None if v is None else str(v)
        elif t == XField.FIELD_INT:
            self.int_value = None if v is None else int(v)
        elif t == XField.FIELD_FLOAT:
            self.float_value = None if v is None else float(v)
        elif t == XField.FIELD_BOOL:
            # نقبل True/False فقط
            if v is None:
                self.bool_value = None
            else:
                self.bool_value = bool(v)
        elif t == XField.FIELD_DATE:
            self.date_value = v  # نتوقع date
        elif t == XField.FIELD_DATETIME:
            self.datetime_value = v  # نتوقع datetime
        elif t in (XField.FIELD_CHOICE, XField.FIELD_MULTI):
            # نخزن قائمة (للـ MULTI) أو قيمة مفردة كـ list بطول 1
            if v is None:
                self.json_value = None
            else:
                if t == XField.FIELD_CHOICE:
                    self.json_value = [v]
                else:
                    # تأكد أنها قائمة
                    self.json_value = list(v) if not isinstance(v, list) else v
        else:
            self.json_value = v

    def __str__(self):
        return f"{self.field.code}={self.value} → {self.content_type.app_label}.{self.content_type.model}#{self.object_id}"
