# base/models/mixins.py
from django.core.exceptions import ValidationError
from django.db import models
from .managers import CompanyScopeManager
from ..company_context import get_company_id


# ---------- أساسية (وقت/تفعيل/عنوان) ----------
class TimeStampedMixin(models.Model):
    """ختم إنشـاء/تعديل مع فهارس."""
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        abstract = True


class ActivableMixin(models.Model):
    """حقل active مع فهرسة."""
    active = models.BooleanField(default=True, db_index=True)

    class Meta:
        abstract = True


class AddressMixin(models.Model):
    """حقول عنوان أساسية (نصية بسيطة كما في Odoo)."""
    street = models.CharField(max_length=255, blank=True)
    street2 = models.CharField(max_length=255, blank=True)
    zip = models.CharField(max_length=24, blank=True)
    city = models.CharField(max_length=128, blank=True)
    state = models.CharField(max_length=128, blank=True)
    country = models.CharField(max_length=128, blank=True)

    class Meta:
        abstract = True


# ---------- شركات وسكوب ----------
class CompanyOwnedMixin(models.Model):
    """
    أي موديل يرث منه سيحصل على:
    - حقل company (مع related_name عام)
    - مدير objects يقيّد الاستعلامات على الشركة النشطة
    - ضبط الشركة تلقائيًا من السياق عند الإنشاء إن لم تُحدد
    - فحص cross-company للعلاقات المذكورة في company_dependent_relations
    """
    company = models.ForeignKey(
        "base.Company",
        on_delete=models.PROTECT,
        related_name="%(app_label)s_%(class)s_set",
        db_index=True,
    )

    # مدير مقيَّد افتراضيًا على الشركة الحالية
    objects = CompanyScopeManager()
    # مدير عام غير مقيَّد عند الحاجة
    all_objects = models.Manager()

    # أسماء الحقول العلائقية التي يجب أن تطابق self.company
    company_dependent_relations: tuple[str, ...] = ()

    class Meta:
        abstract = True
        indexes = [models.Index(fields=["company"])]

    def clean(self):
        super().clean()
        # تحقق cross-company عام
        for rel_name in getattr(self, "company_dependent_relations", ()):
            rel = getattr(self, rel_name, None)
            if not rel:
                continue
            related_company_id = getattr(rel, "company_id", None)
            if related_company_id and related_company_id != self.company_id:
                raise ValidationError({rel_name: "Related record belongs to a different company."})

    def save(self, *args, **kwargs):
        # اضبط company من سياق الجلسة إن لم تُملأ
        if not self.company_id:
            cid = get_company_id()
            if cid:
                self.company_id = cid
        return super().save(*args, **kwargs)


# ---------- تتبّع المستخدم (create_uid/write_uid على طريقة Odoo) ----------
class UserStampedMixin(models.Model):
    """حقول created_by / updated_by مرتبطة بمستخدم base.User."""
    created_by = models.ForeignKey(
        "base.User",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="%(class)s_created",
    )
    updated_by = models.ForeignKey(
        "base.User",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="%(class)s_updated",
    )

    class Meta:
        abstract = True


# ---------- Aliases للتوافق مع كود HR الحالي ----------
# (حتى لو كان كودك في hr يستخدم TimeStamped/UserStamped، لن تحتاج لتعديل كبير)
class TimeStamped(TimeStampedMixin):
    class Meta:
        abstract = True


class UserStamped(UserStampedMixin):
    class Meta:
        abstract = True
