# hr/models/department.py
from django.db import models
from django.core.exceptions import ValidationError

from base.models.mixins import (
    CompanyOwnedMixin,
    TimeStamped,
    UserStamped,
    ActivableMixin,  # يوفر الحقل active افتراضيًا
)


class Department(CompanyOwnedMixin, ActivableMixin, TimeStamped, UserStamped, models.Model):
    """
    Odoo-like hr.department

    التعديلات الأساسية:
    - member_count: مُحتسب (مثل Odoo) بدل total_employee المحفوظ.
      أبقينا total_employee كحقل تراثي (legacy) لتوافق أي كود قديم/إشارات حالية، لكن لا نعتمد عليه.
    - فهرس مركّب (company, parent) لتسريع الاستعلامات الهرمية.
    - استعمال ActivableMixin لحقل active.
    """
    name = models.CharField(max_length=255)

    # ملاحظة: الحقل active يأتي من ActivableMixin

    company = models.ForeignKey(
        "base.Company",
        on_delete=models.PROTECT,
        related_name="departments",
    )

    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,  # منع كسر الهرم
        related_name="children",
    )

    manager = models.ForeignKey(
        "hr.Employee",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="managed_departments",
    )

    # العلاقات التي يجب أن تطابق الشركة
    company_dependent_relations = ("parent", "manager")

    # مسارات/أسماء كاملة للشجرة
    complete_name = models.CharField(max_length=1024, blank=True, db_index=True)
    parent_path = models.CharField(max_length=2048, blank=True, db_index=True)

    # خصائص إضافية اختيارية (كما في Odoo)
    note = models.TextField(blank=True)
    color = models.IntegerField(default=0)

    class Meta:
        db_table = "hr_department"
        indexes = [
            # للاستعلامات حسب الشركة والحالة (active) — active يأتي من ActivableMixin
            models.Index(fields=["company", "active"]),
            # لتسريع استعلامات الشجرة
            models.Index(fields=["company", "parent"]),
            models.Index(fields=["parent_path"]),
            models.Index(fields=["complete_name"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "name"],
                name="uniq_department_name_per_company",
            ),
        ]
        ordering = ("complete_name", "name")

    # ========= عدّ مُحتسب بأسلوب Odoo =========
    @property
    def member_count(self) -> int:
        """
        مطابق لمنطق Odoo: عدّ الموظفين النشِطين داخل القسم.
        لا يُحفظ في DB. استخدمه بدل total_employee في الواجهات/التقارير.
        """
        # Employee.active == True فقط
        return self.members.filter(active=True).count()

    # (اختياري) إبقاء alias من أجل توافق مؤقت مع أي قوالب قديمة
    @property
    def member_count_all(self) -> int:
        """إن أردت عدّ كل الأعضاء بغضّ النظر عن active."""
        return self.members.count()

    # ======== منطق الشجرة (same idea as Odoo) ========
    def _recompute_lineage_fields(self):
        """احسب complete_name و parent_path للقسم الحالي فقط."""
        names, ids = [self.name], [str(self.pk)] if self.pk else [""]
        p = self.parent
        while p:
            names.insert(0, p.name)
            ids.insert(0, str(p.pk))
            p = p.parent
        self.complete_name = " / ".join(names)
        self.parent_path = "/".join(ids) + "/"

    def _recompute_subtree(self):
        """
        أعِد حساب complete_name/parent_path لكل الفروع (DFS).
        يفترض أن complete_name/parent_path للحالي صحيحان قبل الاستدعاء.
        """
        stack = list(self.children.all().only("pk", "name", "parent"))
        while stack:
            node = stack.pop()
            names, ids = [node.name], [str(node.pk)]
            p = node.parent
            while p:
                names.insert(0, p.name)
                ids.insert(0, str(p.pk))
                p = p.parent
            node.complete_name = " / ".join(names)
            node.parent_path = "/".join(ids) + "/"
            node.save(update_fields=["complete_name", "parent_path"])
            stack.extend(list(node.children.all().only("pk", "name", "parent")))

    # ======== lifecycle ========
    def save(self, *args, **kwargs):
        # احفظ أولًا لضمان وجود PK عند الحسابات
        super().save(*args, **kwargs)

        # 1) أعِد حساب القسم الحالي (اسم المسار والشجرة)
        self._recompute_lineage_fields()

        # لم نعد نحدّث total_employee هنا — العدّ صار member_count مُحتسبًا.
        super().save(update_fields=["complete_name", "parent_path"])

        # 2) أعِد بناء المتتاليات لكل الأبناء
        self._recompute_subtree()

        # 3) مزامنة مدير موظفي القسم عند تغيير manager (كما كان)
        #    نعمل مقارنة قديمة/جديدة عبر استعلام خفيف
        try:
            if self.pk:
                old_manager_id = type(self).objects.only("manager_id").get(pk=self.pk).manager_id
            else:
                old_manager_id = None
        except type(self).DoesNotExist:
            old_manager_id = None

        if old_manager_id != getattr(self.manager, "id", None):
            from django.apps import apps
            Employee = apps.get_model("hr", "Employee")
            # حسّن تعيين المدير لجميع موظفي القسم النشطين
            Employee.objects.filter(department=self, active=True) \
                .exclude(manager=self.manager) \
                .update(manager=self.manager)

    # ======== التحقق ========
    def clean(self):
        super().clean()

        # التحقق من توافق الشركة بين القسم والأب/المدير
        if self.parent and self.parent.company_id != self.company_id:
            raise ValidationError({"company": "Parent department must belong to the same company."})

        # منع الدوران (Cyclic) في الهرم
        node = self.parent
        while node:
            if node.pk == self.pk:
                raise ValidationError({"parent": "Cyclic department hierarchy is not allowed."})
            node = node.parent

    def __str__(self):
        return self.complete_name or self.name
