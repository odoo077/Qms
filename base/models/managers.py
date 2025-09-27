# base/models/managers.py
# مدير يقيّد الاستعلام افتراضيًا بـ company_id = current_company، ويتيح إلغاء التقييد عند الحاجة.
from django.db import models
from ..company_context import get_company_id, get_allowed_company_ids

class CompanyScopeQuerySet(models.QuerySet):
    def _apply_company_scope(self):
        cid = get_company_id()
        if cid is None:
            return self
        # فحص آمن لوجود الحقل بدون إثارة استثناء
        has_company_field = any(f.name == "company" for f in self.model._meta.get_fields())
        if has_company_field:
            return self.filter(company_id=cid)
        return self

    # تسهيلات شائعة
    def for_current_company(self):
        return self._apply_company_scope()

    def for_allowed_companies(self):
        allowed = get_allowed_company_ids()
        if allowed and self.model._meta.get_field("company"):
            return self.filter(company_id__in=allowed)
        return self

class CompanyScopeManager(models.Manager.from_queryset(CompanyScopeQuerySet)):
    use_in_migrations = True

    def get_queryset(self):
        qs = super().get_queryset()
        return qs._apply_company_scope()

    # للوصول بدون أي تقييد (حذر!)
    def all_companies(self):
        return super().get_queryset()
