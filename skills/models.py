# ============================================================
# Skills & Resume — Odoo-like data model (FINAL)
# - متوافق مع base + hr
# - بدون ACL / Permissions
# ============================================================

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, UniqueConstraint, CheckConstraint, F
from django.utils.translation import gettext_lazy as _

from base.models import Company, CompanyScopeManager

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
# Company Skill
# ============================================================

class CompanySkill(TimeUserStampedMixin):
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="company_skills", db_index=True
    )
    skill = models.ForeignKey(
        Skill, on_delete=models.CASCADE, related_name="company_skills", db_index=True
    )
    active = models.BooleanField(_("Active"), default=True)

    class Meta:
        verbose_name = _("Company Skill")
        verbose_name_plural = _("Company Skills")
        constraints = [
            UniqueConstraint(
                fields=["company", "skill"],
                name="companyskill_unique_company_skill",
            ),
        ]
        indexes = [
            models.Index(fields=["company", "active"], name="cs_company_active"),
            models.Index(fields=["skill", "active"], name="cs_skill_active"),
        ]

    def __str__(self) -> str:
        return f"{self.company} · {self.skill}"


# ============================================================
# Job Required Skill
# ============================================================

class JobSkill(TimeUserStampedMixin):
    job = models.ForeignKey(
        "hr.Job",
        on_delete=models.CASCADE,
        related_name="required_skills",
        db_index=True,
    )
    skill = models.ForeignKey(
        Skill,
        on_delete=models.PROTECT,
        related_name="job_requirements",
        db_index=True,
    )
    min_level = models.ForeignKey(
        SkillLevel,
        on_delete=models.PROTECT,
        related_name="job_requirements",
    )
    active = models.BooleanField(_("Active"), default=True)

    class Meta:
        verbose_name = _("Job Required Skill")
        verbose_name_plural = _("Job Required Skills")
        ordering = ("job__name", "skill__name")
        constraints = [
            UniqueConstraint(
                fields=["job", "skill"],
                name="jobskill_unique_job_skill",
            ),
        ]

    def clean(self):
        super().clean()
        if self.skill and self.min_level:
            if self.skill.skill_type_id != self.min_level.skill_type_id:
                raise ValidationError({
                    "min_level": _("Minimum level must belong to the same skill type as the selected skill.")
                })

    def __str__(self) -> str:
        return f"{self.job} → {self.skill} (≥ {self.min_level})"


# ============================================================
# Employee Skill
# ============================================================

class EmployeeSkill(TimeUserStampedMixin):
    employee = models.ForeignKey(
        "hr.Employee",
        on_delete=models.CASCADE,
        related_name="skills",
        db_index=True,
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

    class Meta:
        verbose_name = _("Employee Skill")
        verbose_name_plural = _("Employee Skills")
        ordering = ("employee__company__name", "employee__name", "skill_type__sequence", "skill__name")
        constraints = [
            UniqueConstraint(
                fields=["employee", "skill"],
                name="employeeskill_unique_employee_skill",
                violation_error_message=_("This employee already has this skill."),
            ),
            CheckConstraint(
                check=Q(valid_to__isnull=True)
                | Q(valid_from__isnull=True)
                | Q(valid_to__gte=F("valid_from")),
                name="employeeskill_valid_to_gte_from_chk",
            ),
        ]

    def clean(self) -> None:
        super().clean()

        if self.skill_id and self.skill_type_id:
            if self.skill.skill_type_id != self.skill_type_id:
                raise ValidationError({"skill": _("Skill must belong to the selected skill type.")})

        if self.skill_level_id and self.skill_type_id:
            if self.skill_level.skill_type_id != self.skill_type_id:
                raise ValidationError({"skill_level": _("Level must belong to the selected skill type.")})

        if self.employee_id and self.skill_id:
            is_enabled = CompanySkill.objects.filter(
                company_id=self.employee.company_id,
                skill_id=self.skill_id,
                active=True,
            ).exists()
            if not is_enabled:
                raise ValidationError({"skill": _("This skill is not enabled for the employee company.")})

    def save(self, *args, **kwargs):
        if self.employee_id:
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

class ResumeLine(TimeUserStampedMixin):
    employee = models.ForeignKey(
        "hr.Employee",
        on_delete=models.CASCADE,
        related_name="resume_lines",
        db_index=True,
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

    class Meta:
        verbose_name = _("Resume Line")
        verbose_name_plural = _("Resume Lines")
        ordering = ("employee__company__name", "employee__name", "line_type__sequence", "date_start")
        constraints = [
            UniqueConstraint(
                fields=["employee", "line_type", "name"],
                name="resumeline_unique_employee_type_name",
            ),
        ]

    def clean(self) -> None:
        super().clean()

        if self.employee and self.company != self.employee.company:
            self.company = self.employee.company

        if self.date_start and self.date_end and self.date_end < self.date_start:
            raise ValidationError({"date_end": _("Date to must be after or equal to Date from.")})

    def save(self, *args, **kwargs):
        if self.employee_id:
            self.company_id = self.employee.company_id
        if self.certificate_file and not self.certificate_filename:
            self.certificate_filename = self.certificate_file.name.rsplit("/", 1)[-1]
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.employee} / {self.line_type}: {self.name}"
