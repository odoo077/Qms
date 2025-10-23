from django.db import models
from django.utils import timezone
from django.db.models import Q
from django.core.exceptions import ValidationError
from base.models import ActivableMixin, TimeStampedMixin, UserStampedMixin


class HrSkillType(ActivableMixin, TimeStampedMixin, UserStampedMixin, models.Model):
    """
    Odoo-like hr.skill.type
    - يمسك مجموعة المهارات ومستوياتها.
    - يدعم وسم 'is_certification' لتمييز الشهادات.
    - levels_count: يُحدّث عبر إشارة (signal) بعد حفظ/حذف HrSkillLevel.
    """
    name = models.CharField(max_length=255, unique=True, db_index=True)
    sequence = models.IntegerField(default=10)
    color = models.IntegerField(default=1)  # 1..11 عادةً في Odoo
    is_certification = models.BooleanField(default=False)

    # يُحدَّث عبر signal (skills/signals/skill_signals.py)
    levels_count = models.PositiveIntegerField(default=0, editable=False)

    class Meta:
        db_table = "hr_skill_type"
        ordering = ("sequence", "name")
        indexes = [
            models.Index(fields=["active"]),
            models.Index(fields=["sequence", "name"]),
        ]

    def clean(self):
        super().clean()
        # ملاحظة: في Odoo يُرفض نوع بلا مهارات/مستويات عند عمليات معينة.
        # هنا نترك التحقق للواجهة/المنطق التطبيقي (أو تضيفه لاحقًا بعد توفّر بيانات كافية).

    def __str__(self):
        return f"{self.name}{' 🏅' if self.is_certification else ''}"


class HrSkillLevel(TimeStampedMixin, UserStampedMixin, models.Model):
    """
    Odoo-like hr.skill.level
    - مستوى تابع لنوع مهارة واحد.
    - default_level: يجب أن يكون واحدًا فقط لكل SkillType (ن enforced في save()).
    """
    skill_type = models.ForeignKey(HrSkillType, on_delete=models.CASCADE, related_name="skill_levels")
    name = models.CharField(max_length=255)
    level_progress = models.PositiveIntegerField(default=0)  # 0..100
    default_level = models.BooleanField(default=False)

    class Meta:
        db_table = "hr_skill_level"
        ordering = ("level_progress", "id")
        unique_together = (("skill_type", "name"),)
        indexes = [
            models.Index(fields=["skill_type"]),
            models.Index(fields=["level_progress"]),
        ]
        constraints = [
            models.CheckConstraint(
                name="skill_level_progress_range",
                check=models.Q(level_progress__gte=0) & models.Q(level_progress__lte=100),
            )
        ]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # enforce "one default per type"
        if self.default_level:
            (type(self).objects
             .filter(skill_type=self.skill_type)
             .exclude(pk=self.pk)
             .update(default_level=False))

    def __str__(self):
        return f"{self.skill_type.name}: {self.name} ({self.level_progress}%)"


class HrSkill(ActivableMixin, TimeStampedMixin, UserStampedMixin, models.Model):
    """
    Odoo-like hr.skill
    - مهارة مرتبطة بنوع.
    - color يُعرض من النوع (property للعرض كما في related).
    """
    name = models.CharField(max_length=255)
    sequence = models.IntegerField(default=10)
    skill_type = models.ForeignKey(HrSkillType, on_delete=models.CASCADE, related_name="skills")

    class Meta:
        db_table = "hr_skill"
        ordering = ("sequence", "name")
        unique_together = (("skill_type", "name"),)
        indexes = [
            models.Index(fields=["active"]),
            models.Index(fields=["skill_type"]),
        ]

    @property
    def color(self) -> int:
        return self.skill_type.color if self.skill_type_id else 1

    def __str__(self):
        return f"{self.name} ({self.skill_type.name})"


class HrResumeLineType(ActivableMixin, TimeStampedMixin, UserStampedMixin, models.Model):
    """
    Odoo-like hr.resume.line.type
    - تعريف أنواع أسطر السيرة (خبرة/تعليم/دورة...).
    - يمكن تعريف خصائص مخصّصة لكل نوع عبر JSON schema بسيط.
    """
    name = models.CharField(max_length=255, unique=True, db_index=True)
    sequence = models.IntegerField(default=10)
    is_course = models.BooleanField(default=False)

    # مخطط اختياري لخصائص سطر السيرة (قائمة مفاتيح/أنواع/إلزامية...)
    properties_definition = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "hr_resume_line_type"
        ordering = ("sequence", "name")
        indexes = [models.Index(fields=["active"]), ]

    def __str__(self):
        return self.name


class HrResumeLine(TimeStampedMixin, UserStampedMixin, models.Model):
    """
    Odoo-like hr.resume.line
    - سطر في CV لموظف (خبرة/تعليم/دورة).
    - company/department تُملآن تلقائيًا من employee عند الحفظ (للتوافق مع تقارير الشركة).
    """
    employee = models.ForeignKey("hr.Employee", on_delete=models.CASCADE, related_name="resume_lines")

    # denorm خفيف للتصفية/التقارير؛ نُحدّثها من employee في save()
    company = models.ForeignKey("base.Company", on_delete=models.PROTECT, related_name="resume_lines", null=True,
                                blank=True)
    department = models.ForeignKey("hr.Department", on_delete=models.SET_NULL, related_name="resume_lines", null=True,
                                   blank=True)

    name = models.CharField(max_length=255, help_text="Title of the experience/course/education item.")
    line_type = models.ForeignKey(HrResumeLineType, on_delete=models.PROTECT, related_name="resume_lines")

    date_start = models.DateField(null=True, blank=True)
    date_end = models.DateField(null=True, blank=True)

    # ملاحظات/تفاصيل (يمكن جعلها HTML في الواجهة)
    description = models.TextField(blank=True)

    # خصائص إضافية حسب تعريف النوع (اختياري)
    properties = models.JSONField(default=dict, blank=True)

    # دورات تدريبية:
    COURSE_TYPES = (
        ("external", "External"),
        ("internal", "Internal"),
    )
    course_type = models.CharField(max_length=16, choices=COURSE_TYPES, default="external")
    external_url = models.URLField(blank=True)

    # شهادة/ملف مرفق اختياري
    certificate_file = models.FileField(upload_to="resume_certificates/", null=True, blank=True)
    certificate_filename = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "hr_resume_line"
        ordering = ("-date_start", "-date_end", "id")
        indexes = [
            models.Index(fields=["employee"]),
            models.Index(fields=["line_type"]),
            models.Index(fields=["date_start", "date_end"]),
        ]

    @property
    def is_course(self) -> bool:
        return bool(self.line_type and self.line_type.is_course)

    def clean(self):
        super().clean()
        # تحقق تواريخ
        if self.date_start and self.date_end and self.date_start > self.date_end:
            raise ValidationError({"date_end": "End date must be on or after start date."})
        # إن لم تكن دورة خارجية → امسح رابط external_url
        if self.course_type != "external" and self.external_url:
            self.external_url = ""

    def save(self, *args, **kwargs):
        # توليد اسم من الـ URL إن الاسم فارغ ولدينا external_url
        if not self.name and self.external_url:
            try:
                from urllib.parse import urlparse
                host = urlparse(self.external_url).netloc
                self.name = host or "External Course"
            except Exception:
                pass

        # company/department من الموظف
        if self.employee_id:
            self.company = self.employee.company
            self.department = self.employee.department

        # حفظ اسم الملف لو تم رفع مرفق
        if self.certificate_file and not self.certificate_filename:
            self.certificate_filename = getattr(self.certificate_file, "name", "") or ""

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.employee.name} · {self.name}"


class HrIndividualSkillMixin(TimeStampedMixin, UserStampedMixin, models.Model):
    """
    Abstract mixin (Odoo-like hr.individual.skill.mixin)
    يحتوي المنطق المشترك:
    - skill_type / skill / skill_level
    - valid_from / valid_to
    - خصائص related: is_certification, level_progress, color
    * تحقق أساسي على التواريخ؛
      منطق منع التداخل لغير الشهادات يُنفَّذ عبر signal/manager خارج هذا الموديل.
    """

    class Meta:
        abstract = True

    skill_type = models.ForeignKey(HrSkillType, on_delete=models.PROTECT, related_name="%(class)s_records")
    skill = models.ForeignKey(HrSkill, on_delete=models.PROTECT, related_name="%(class)s_records")
    skill_level = models.ForeignKey(HrSkillLevel, on_delete=models.PROTECT, related_name="%(class)s_records")

    valid_from = models.DateField()
    valid_to = models.DateField(null=True, blank=True)

    def clean(self):
        super().clean()
        # المهارة والمستوى يجب أن يتبعا نفس النوع
        if self.skill_id and self.skill_type_id and self.skill.skill_type_id != self.skill_type_id:
            raise ValidationError({"skill": "Skill must belong to the selected skill type."})
        if self.skill_level_id and self.skill_type_id and self.skill_level.skill_type_id != self.skill_type_id:
            raise ValidationError({"skill_level": "Level must belong to the selected skill type."})
        # valid_from <= valid_to
        if self.valid_to and self.valid_from and self.valid_from > self.valid_to:
            raise ValidationError({"valid_to": "valid_to must be on or after valid_from."})

    # === Related-style properties (عرض فقط) ===
    @property
    def is_certification(self) -> bool:
        return bool(self.skill_type and self.skill_type.is_certification)

    @property
    def level_progress(self) -> int:
        return self.skill_level.level_progress if self.skill_level_id else 0

    @property
    def color(self) -> int:
        return self.skill_type.color if self.skill_type_id else 1


class HrEmployeeSkill(HrIndividualSkillMixin, TimeStampedMixin, UserStampedMixin, models.Model):
    """
    Odoo-like hr.employee.skill
    يربط موظفًا بمهارة/مستوى/فترة.
    - منطق منع التداخل لغير الشهادات موجود في signal (employee_skill_signals.py).
    - وفّرنا مدير مساعد لإرجاع “المهارات الحالية” للموظف.
    """
    employee = models.ForeignKey("hr.Employee", on_delete=models.CASCADE, related_name="skills")

    class Meta:
        db_table = "hr_employee_skill"
        ordering = ("skill_type", "skill", "skill_level", "valid_from", "id")
        indexes = [
            models.Index(fields=["employee"]),
            models.Index(fields=["skill"]),
            models.Index(fields=["skill_type"]),
            models.Index(fields=["skill_level"]),
        ]
        # لا نضع unique_together صارمًا لأن الشهادات قد تتكرر بفترات مختلفة.
        permissions = [
            ("rate_skill", "Can rate employee skill"),
        ]

    def __str__(self):
        return f"{self.employee.name} · {self.skill.name} ({self.skill_level.name})"

    # === Manager helpers (static/class methods) ===
    @staticmethod
    def current_for_employee(employee_id, on_date=None):
        """
        يعيد QuerySet للمهارات النشطة لموظف في تاريخ معيّن (اليوم افتراضيًا).
        - لغير الشهادات: سجل واحد نشط لكل Skill (تُغطيه قيود/signals).
        - للشهادات: يعيد السجلات التي يغطي نطاقها التاريخ.
        """
        on_date = on_date or timezone.now().date()
        qs = (HrEmployeeSkill.objects
              .filter(employee_id=employee_id)
              .filter(Q(valid_from__lte=on_date) & (Q(valid_to__isnull=True) | Q(valid_to__gte=on_date))))
        return qs
