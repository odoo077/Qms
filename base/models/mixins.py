# base/models/mixins.py
from django.core.exceptions import ValidationError
from django.db import models
from .managers import CompanyScopeManager
from ..company_context import get_company_id

class TimeStampedMixin(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        abstract = True


class ActivableMixin(models.Model):
    active = models.BooleanField(default=True, db_index=True)

    class Meta:
        abstract = True


class AddressMixin(models.Model):
    street = models.CharField(max_length=255, blank=True)
    street2 = models.CharField(max_length=255, blank=True)
    zip = models.CharField(max_length=24, blank=True)
    city = models.CharField(max_length=128, blank=True)
    state = models.CharField(max_length=128, blank=True)
    country = models.CharField(max_length=128, blank=True)

    class Meta:
        abstract = True


class CompanyOwnedMixin(models.Model):
    """
    أي موديل يرث منه سيحصل على:
    - حقل company
    - مدير objects يقيّد على الشركة النشطة
    - ضبط الشركة الافتراضية عند الإنشاء لو لم تُحدد
    - فحص cross-company للعلاقات المعرفة في company_dependent_relations
    """
    company = models.ForeignKey("base.Company", on_delete=models.PROTECT, related_name="%(app_label)s_%(class)s_set", db_index=True)

    # مدير مقيّد افتراضيًا
    objects = CompanyScopeManager()
    # مدير غير مقيّد عند الحاجة (للأدمن/الخدمات)
    all_objects = models.Manager()

    # أسماء الحقول العلائقية التي يجب أن تتطابق شركاتها مع self.company
    company_dependent_relations: tuple[str, ...] = ()

    class Meta:
        abstract = True
        indexes = [models.Index(fields=["company"])]

    def clean(self):
        super().clean()
        # تحقق cross-company الأساسي
        for rel_name in getattr(self, "company_dependent_relations", ()):
            rel = getattr(self, rel_name, None)
            if rel is None:
                continue
            # يدعم FK أو OneToOne
            related_company_id = getattr(rel, "company_id", None)
            if related_company_id and related_company_id != self.company_id:
                raise ValidationError({rel_name: "Related record belongs to a different company."})

    def save(self, *args, **kwargs):
        # اضبط الشركة افتراضياً من السياق إن لم تُمرر
        if not self.company_id:
            cid = get_company_id()
            if cid:
                self.company_id = cid
        return super().save(*args, **kwargs)