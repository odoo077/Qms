# skills/models.py
# ============================================================
# Skills & Resume — Odoo-like data model
# - مطابق لمنطق Odoo (hr_skill, hr_employee_skill, hr_resume_line*)
# - متوافق مع django-guardian (لا حاجة لحقول إضافية)
# - تعليقات عربية لسهولة الصيانة
# ============================================================

from __future__ import annotations

from typing import Optional

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, UniqueConstraint, CheckConstraint
from django.utils.translation import gettext_lazy as _
from base.acl import AccessControlledMixin

# ------------------------------------------------------------
# روابط للتطبيقات الأساسية (حسب مشروعك)
# ------------------------------------------------------------
# Company و Employee مأخوذان من تطبيقاتك الحالية:
from base.models import Company, CompanyScopeManager  # شركتك
from hr.models import Employee   # موظفك


# ============================================================
# Helpers / Mixins
# ============================================================

User = get_user_model()


class TimeUserStampedMixin(models.Model):
    """
    مكسن بسيط لإضافة طوابع الإنشاء والتعديل + المستخدم المُنشئ/المُعدّل.
    - لا يتدخل في صلاحيات Guardian (تُدار عبر signals/admin).
    """
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="%(class)s_created"
    )
    updated_at = models.DateTimeField(auto_now=True, editable=False)
    updated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="%(class)s_updated"
    )

    class Meta:
        abstract = True


# ============================================================
# Skill Type
# ============================================================

class SkillType(TimeUserStampedMixin):
    """
    نوع المهارة (Odoo: hr.skill.type)
    - مثال: "Programming", "Language", "Certification"
    """
    name = models.CharField(_("Name"), max_length=128, unique=True)
    sequence = models.PositiveIntegerField(_("Sequence"), default=10, db_index=True)
    color = models.PositiveSmallIntegerField(_("Color Index"), default=0)  # مثل Odoo (0..11 عادة)
    is_certification = models.BooleanField(_("Is certification?"), default=False)
    active = models.BooleanField(_("Active"), default=True)

    # عدد المستويات لهذا النوع (حقل محسوب-مخزّن اختياري في Odoo؛ سنتركه خصيصة property)
    class Meta:
        verbose_name = _("Skill Type")
        verbose_name_plural = _("Skill Types")
        ordering = ("sequence", "name")
        indexes = [
            models.Index(fields=["active", "sequence"], name="skilltype_active_seq_idx"),
        ]

    def __str__(self) -> str:
        return self.name

    @property
    def levels_count(self) -> int:
        """عدد المستويات المرتبطة بهذا النوع."""
        return self.levels.filter(active=True).count()


# ============================================================
# Skill Level
# ============================================================

class SkillLevel(TimeUserStampedMixin):
    """
    مستوى المهارة (Odoo: hr.skill.level)
    - مرتبط بنوع مهارة واحد.
    - level_progress من 0 إلى 100.
    - default_level مستوى افتراضي وحيد لكل نوع.
    """
    skill_type = models.ForeignKey(
        SkillType, on_delete=models.CASCADE, related_name="levels", db_index=True
    )
    name = models.CharField(_("Name"), max_length=128)
    level_progress = models.PositiveSmallIntegerField(_("Progress (0..100)"), default=0)
    default_level = models.BooleanField(_("Default for type"), default=False)
    active = models.BooleanField(_("Active"), default=True)

    class Meta:
        verbose_name = _("Skill Level")
        verbose_name_plural = _("Skill Levels")
        ordering = ("skill_type__sequence", "level_progress", "name")
        constraints = [
            # تحقق من النطاق 0..100
            CheckConstraint(
                check=Q(level_progress__gte=0) & Q(level_progress__lte=100),
                name="skilllevel_progress_0_100_chk",
            ),
            # اسم المستوى فريد داخل نفس النوع
            UniqueConstraint(
                fields=["skill_type", "name"],
                name="skilllevel_unique_name_per_type",
            ),
            # تقدّم المستوى فريد داخل نفس النوع (اختياري لكنه شائع)
            UniqueConstraint(
                fields=["skill_type", "level_progress"],
                name="skilllevel_unique_progress_per_type",
            ),
            # مستوى افتراضي وحيد لكل نوع (شرطي)
            UniqueConstraint(
                fields=["skill_type", "default_level"],
                condition=Q(default_level=True),
                name="skilllevel_single_default_per_type",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.skill_type.name} / {self.name} ({self.level_progress}%)"


# ============================================================
# Skill
# ============================================================

class Skill(TimeUserStampedMixin):
    """
    مهارة محددة داخل نوع (Odoo: hr.skill)
    - مثال: نوع "Programming" ⇒ مهارات: "Python", "Django"
    """
    skill_type = models.ForeignKey(
        SkillType, on_delete=models.CASCADE, related_name="skills", db_index=True
    )
    name = models.CharField(_("Name"), max_length=128)
    sequence = models.PositiveIntegerField(_("Sequence"), default=10, db_index=True)
    active = models.BooleanField(_("Active"), default=True)

    class Meta:
        verbose_name = _("Skill")
        verbose_name_plural = _("Skills")
        ordering = ("skill_type__sequence", "sequence", "name")
        constraints = [
            UniqueConstraint(
                fields=["skill_type", "name"],
                name="skill_unique_name_per_type",
            ),
        ]
        indexes = [
            models.Index(fields=["active", "skill_type"], name="skill_active_type_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.skill_type.name} / {self.name}"


# ============================================================
# Employee Skill (Odoo: hr.employee.skill)
# ============================================================

class EmployeeSkill(TimeUserStampedMixin, AccessControlledMixin):
    """
    مهارة موظف:
    - employee + (skill_type, skill, skill_level)
    - company (denorm) لتمكين نطاق الشركة والفلترة السريعة (منطق Odoo).
    - التحقق: skill & level يجب أن ينتميا لنفس skill_type المختار.
    """
    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="skills", db_index=True
    )
    company = models.ForeignKey(  # denorm من employee لتسهيل التقارير و ACLs
        Company, on_delete=models.PROTECT, null=True, blank=True, db_index=True
    )

    skill_type = models.ForeignKey(
        SkillType, on_delete=models.PROTECT, related_name="employee_skills", db_index=True
    )
    skill = models.ForeignKey(
        Skill, on_delete=models.PROTECT, related_name="employee_skills", db_index=True
    )
    skill_level = models.ForeignKey(
        SkillLevel, on_delete=models.PROTECT, related_name="employee_skills", db_index=True
    )

    valid_from = models.DateField(_("Valid from"), null=True, blank=True)
    valid_to = models.DateField(_("Valid to"), null=True, blank=True)
    note = models.TextField(_("Note"), blank=True, default="")
    active = models.BooleanField(_("Active"), default=True)

    objects = CompanyScopeManager()

    class Meta:
        verbose_name = _("Employee Skill")
        verbose_name_plural = _("Employee Skills")
        ordering = ("employee__company__name", "employee__name", "skill_type__sequence", "skill__name")
        # صلاحية مخصصة (سيفيدك مع Guardian)
        permissions = [
            ("rate_skill", "Can rate/evaluate employee skill"),
        ]
        constraints = [
            UniqueConstraint(
                fields=["employee", "skill"],
                name="employeeskill_unique_employee_skill",
                violation_error_message=_("This employee already has this skill."),
            ),
            # ✅ أبقِ فقط قيد التاريخ (لا وجود لأي joined fields هنا)
            CheckConstraint(
                check=Q(valid_to__isnull=True) | Q(valid_from__isnull=True) | Q(valid_to__gte=models.F("valid_from")),
                name="employeeskill_valid_to_gte_from_chk",
            ),
        ]

        indexes = [
            # فهرس الشركة + الموظف + الحالة (اسم مختصر)
            models.Index(fields=["company", "employee", "active"], name="es_comp_emp_act_idx"),
            # فهرس النوع + المستوى (اسم مختصر)
            models.Index(fields=["skill_type", "skill_level"], name="es_type_lvl_idx"),
        ]

    # ---------- تنظيف/تحقق إضافي ----------
    def clean(self) -> None:
        super().clean()

        # (1) skill & level يجب أن يطابقا skill_type
        if self.skill and self.skill_type and self.skill.skill_type_id != self.skill_type_id:
            raise ValidationError({"skill": _("Skill must belong to the selected skill type.")})
        if self.skill_level and self.skill_type and self.skill_level.skill_type_id != self.skill_type_id:
            raise ValidationError({"skill_level": _("Level must belong to the selected skill type.")})

        # (2) company denorm = employee.company
        if self.employee and self.employee.company and self.company != self.employee.company:
            self.company = self.employee.company

        # (3) منع تداخل الفترات الزمنية لنفس (employee, skill_type) إن رغبت (اختياري)
        # if self.valid_from and self.valid_to:
        #     overlap = EmployeeSkill.objects.filter(
        #         employee=self.employee, skill_type=self.skill_type
        #     ).exclude(pk=self.pk).filter(
        #         valid_from__lte=self.valid_to, valid_to__gte=self.valid_from
        #     ).exists()
        #     if overlap:
        #         raise ValidationError(_("Overlapping validity period for this skill type."))

    def save(self, *args, **kwargs):
        # denorm للشركة من الموظف دائمًا (مثل Odoo)
        if self.employee_id and self.employee.company_id and self.company_id != self.employee.company_id:
            self.company_id = self.employee.company_id
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.employee} / {self.skill} → {self.skill_level}"


# ============================================================
# Resume Line Type (Odoo: hr.resume.line.type)
# ============================================================

class ResumeLineType(TimeUserStampedMixin):
    """
    نوع سطر السيرة الذاتية:
    - أمثلة: 'Experience', 'Education', 'Certification'
    - properties_definition: مساحة مرنة لتعريف حقول إضافية لكل نوع (بديل Odoo properties)
    """
    name = models.CharField(_("Name"), max_length=128, unique=True)
    sequence = models.PositiveIntegerField(_("Sequence"), default=10, db_index=True)
    active = models.BooleanField(_("Active"), default=True)

    # JSON لتعريف خصائص إضافية حسب حاجتك (مكافئ Odoo properties)
    properties_definition = models.JSONField(_("Properties schema"), default=dict, blank=True)

    class Meta:
        verbose_name = _("Resume Line Type")
        verbose_name_plural = _("Resume Line Types")
        ordering = ("sequence", "name")
        indexes = [
            models.Index(fields=["active", "sequence"], name="resumelinetype_active_seq_idx"),
        ]

    def __str__(self) -> str:
        return self.name


# ============================================================
# Resume Line (Odoo: hr.resume.line)
# ============================================================

class ResumeLine(TimeUserStampedMixin):
    """
    سطر السيرة الذاتية للموظف:
    - يَجمع نوع السطر + نص/تفاصيل + فترة من/إلى + مرفقات اختيارية.
    - company denorm من employee (كما في Odoo عبر السياق).
    """
    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="resume_lines", db_index=True
    )
    company = models.ForeignKey(  # denorm لفلترة الشركة بسهولة
        Company, on_delete=models.PROTECT, null=True, blank=True, db_index=True
    )
    line_type = models.ForeignKey(
        ResumeLineType, on_delete=models.PROTECT, related_name="lines", db_index=True
    )

    name = models.CharField(_("Title / Summary"), max_length=256)
    description = models.TextField(_("Description / Details"), blank=True, default="")
    date_start = models.DateField(_("Date from"), null=True, blank=True)
    date_end = models.DateField(_("Date to"), null=True, blank=True)

    # إضافات عملية (اختيارية)
    certificate_file = models.FileField(upload_to="resume/certificates/", blank=True, null=True)
    certificate_filename = models.CharField(max_length=256, blank=True, default="")
    external_url = models.URLField(blank=True, default="")

    active = models.BooleanField(_("Active"), default=True)

    objects = CompanyScopeManager()

    class Meta:
        verbose_name = _("Resume Line")
        verbose_name_plural = _("Resume Lines")
        ordering = ("employee__company__name", "employee__name", "line_type__sequence", "date_start")
        indexes = [
            # فهرس الشركة + الموظف + الحالة (اسم مختصر)
            models.Index(fields=["company", "employee", "active"], name="rl_comp_emp_act_idx"),
            # فهرس نوع السطر + الحالة (اسم مختصر)
            models.Index(fields=["line_type", "active"], name="rl_type_act_idx"),
        ]

    def clean(self) -> None:
        super().clean()

        # denorm للشركة من الموظف
        if self.employee and self.employee.company and self.company != self.employee.company:
            self.company = self.employee.company

        # تحقق منطقي من التاريخ
        if self.date_start and self.date_end and self.date_end < self.date_start:
            raise ValidationError({"date_end": _("Date to must be after or equal to Date from.")})

    def save(self, *args, **kwargs):
        if self.employee_id and self.employee.company_id and self.company_id != self.employee.company_id:
            self.company_id = self.employee.company_id
        # اسم الملف لأغراض العرض السريع
        if self.certificate_file and not self.certificate_filename:
            self.certificate_filename = self.certificate_file.name.rsplit("/", 1)[-1]
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.employee} / {self.line_type}: {self.name}"
