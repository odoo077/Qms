# skills/models.py
# ============================================================
# Skills & Resume — Odoo-like data model (FINAL)
# - متوافق مع base + hr + ACL
# - جاهز للإنتاج
# ============================================================

from __future__ import annotations

from typing import Optional

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, UniqueConstraint, CheckConstraint, F
from django.utils.translation import gettext_lazy as _

from base.acl import AccessControlledMixin, ACLManager
from base.models import Company, CompanyScopeManager
from hr.models import Employee

User = get_user_model()


# ============================================================
# Mixins
# ============================================================

class TimeUserStampedMixin(models.Model):
    """
    طوابع زمنية + المستخدم المنشئ/المعدّل
    """
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="%(class)s_created"
    )
    updated_at = models.DateTimeField(auto_now=True, editable=False)
    updated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="%(class)s_updated"
    )

    class Meta:
        abstract = True


# ============================================================
# Skill Type
# ============================================================

class SkillType(TimeUserStampedMixin):
    name = models.CharField(_("Name"), max_length=128, unique=True)
    sequence = models.PositiveIntegerField(_("Sequence"), default=10, db_index=True)
    color = models.PositiveSmallIntegerField(_("Color Index"), default=0)
    is_certification = models.BooleanField(_("Is certification?"), default=False)
    active = models.BooleanField(_("Active"), default=True)

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
        return self.levels.filter(active=True).count()


# ============================================================
# Skill Level
# ============================================================

class SkillLevel(TimeUserStampedMixin):
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
            CheckConstraint(
                check=Q(level_progress__gte=0) & Q(level_progress__lte=100),
                name="skilllevel_progress_0_100_chk",
            ),
            UniqueConstraint(
                fields=["skill_type", "name"],
                name="skilllevel_unique_name_per_type",
            ),
            UniqueConstraint(
                fields=["skill_type", "level_progress"],
                name="skilllevel_unique_progress_per_type",
            ),
            UniqueConstraint(
                fields=["skill_type"],
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

    def __str__(self) -> str:
        return f"{self.skill_type.name} / {self.name}"


# ============================================================
# Employee Skill
# ============================================================

class EmployeeSkill(TimeUserStampedMixin, AccessControlledMixin):
    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="skills", db_index=True
    )
    company = models.ForeignKey(
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
    acl = ACLManager()

    class Meta:
        verbose_name = _("Employee Skill")
        verbose_name_plural = _("Employee Skills")
        ordering = ("employee__company__name", "employee__name", "skill_type__sequence", "skill__name")
        permissions = [
            ("rate_skill", "Can rate/evaluate employee skill"),
        ]
        constraints = [
            # قيد التفرد الصحيح (Company + Employee + Skill)
            UniqueConstraint(
                fields=["company", "employee", "skill"],
                name="employeeskill_unique_company_employee_skill",
                violation_error_message=_("This employee already has this skill."),
            ),
            CheckConstraint(
                check=Q(valid_to__isnull=True)
                | Q(valid_from__isnull=True)
                | Q(valid_to__gte=F("valid_from")),
                name="employeeskill_valid_to_gte_from_chk",
            ),
        ]

    # NOTE:
    # company is ALWAYS derived from employee.company.
    # Any provided company value will be overridden for data integrity.
    def clean(self) -> None:
        super().clean()

        # (1) تطابق النوع
        if self.skill and self.skill_type and self.skill.skill_type_id != self.skill_type_id:
            raise ValidationError({"skill": _("Skill must belong to the selected skill type.")})
        if self.skill_level and self.skill_type and self.skill_level.skill_type_id != self.skill_type_id:
            raise ValidationError({"skill_level": _("Level must belong to the selected skill type.")})

        # (2) توحيد الشركة مع الموظف
        if self.employee and self.company != self.employee.company:
            self.company = self.employee.company

    def save(self, *args, **kwargs):
        if self.employee_id and self.employee.company_id:
            self.company_id = self.employee.company_id
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.employee} / {self.skill} → {self.skill_level}"


# ============================================================
# Resume Line Type
# ============================================================

class ResumeLineType(TimeUserStampedMixin):
    name = models.CharField(_("Name"), max_length=128, unique=True)
    sequence = models.PositiveIntegerField(_("Sequence"), default=10, db_index=True)
    active = models.BooleanField(_("Active"), default=True)
    properties_definition = models.JSONField(_("Properties schema"), default=dict, blank=True)

    class Meta:
        verbose_name = _("Resume Line Type")
        verbose_name_plural = _("Resume Line Types")
        ordering = ("sequence", "name")

    def __str__(self) -> str:
        return self.name


# ============================================================
# Resume Line
# ============================================================

class ResumeLine(TimeUserStampedMixin, AccessControlledMixin):
    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="resume_lines", db_index=True
    )
    company = models.ForeignKey(
        Company, on_delete=models.PROTECT, null=True, blank=True, db_index=True
    )
    line_type = models.ForeignKey(
        ResumeLineType, on_delete=models.PROTECT, related_name="lines", db_index=True
    )

    name = models.CharField(_("Title / Summary"), max_length=256)
    description = models.TextField(_("Description / Details"), blank=True, default="")
    date_start = models.DateField(_("Date from"), null=True, blank=True)
    date_end = models.DateField(_("Date to"), null=True, blank=True)

    certificate_file = models.FileField(upload_to="resume/certificates/", blank=True, null=True)
    certificate_filename = models.CharField(max_length=256, blank=True, default="")
    external_url = models.URLField(blank=True, default="")
    active = models.BooleanField(_("Active"), default=True)

    objects = CompanyScopeManager()
    acl = ACLManager()

    class Meta:
        verbose_name = _("Resume Line")
        verbose_name_plural = _("Resume Lines")
        ordering = ("employee__company__name", "employee__name", "line_type__sequence", "date_start")

    # NOTE:
    # company is enforced from employee.company to keep multi-company integrity.
    def clean(self) -> None:
        super().clean()

        # توحيد الشركة مع الموظف
        if self.employee and self.company != self.employee.company:
            self.company = self.employee.company

        if self.date_start and self.date_end and self.date_end < self.date_start:
            raise ValidationError({"date_end": _("Date to must be after or equal to Date from.")})

    def save(self, *args, **kwargs):
        if self.employee_id and self.employee.company_id:
            self.company_id = self.employee.company_id
        if self.certificate_file and not self.certificate_filename:
            self.certificate_filename = self.certificate_file.name.rsplit("/", 1)[-1]
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.employee} / {self.line_type}: {self.name}"
