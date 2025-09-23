from django.db import models
from django.core.exceptions import ValidationError
from .mixins import TimeStamped
from .skill_type import HrSkillType
from .skill_level import HrSkillLevel
from .skill import HrSkill
from datetime import date

class HrIndividualSkillMixin(TimeStamped):
    """
    Abstract Odoo-like skill model with versioning & validity logic.
    Mirrors: fields, constraints, and 'archive-on-change' ideas. :contentReference[oaicite:15]{index=15}
    """
    class Meta:
        abstract = True
        ordering = ["skill_type_id_id", "skill_level_id_id"]  # mimic Odoo ordering

    # Core / active fields (Odoo: store=True + domains) :contentReference[oaicite:16]{index=16}
    skill_type = models.ForeignKey(HrSkillType, on_delete=models.CASCADE)
    skill = models.ForeignKey(HrSkill, on_delete=models.CASCADE)
    skill_level = models.ForeignKey(HrSkillLevel, on_delete=models.CASCADE)

    # Validity window
    valid_from = models.DateField(default=date.today)
    valid_to = models.DateField(null=True, blank=True)

    # Related helpers (Odoo: related) :contentReference[oaicite:17]{index=17}
    @property
    def level_progress(self) -> int:
        return self.skill_level.level_progress if self.skill_level_id else 0

    @property
    def color(self) -> int:
        return self.skill_type.color if self.skill_type_id else 0

    @property
    def levels_count(self) -> int:
        return self.skill_type.levels_count if self.skill_type_id else 0

    @property
    def is_certification(self) -> bool:
        return bool(self.skill_type and self.skill_type.is_certification)

    # Display name (Odoo compute) :contentReference[oaicite:18]{index=18}
    @property
    def display_name(self) -> str:
        if not (self.skill_id and self.skill_level_id):
            return ""
        return f"{self.skill.name}: {self.skill_level.name}"

    # --- Constraints mirroring Odoo’s behavior ---
    def clean(self):
        super().clean()
        # Date order check (valid_from <= valid_to) :contentReference[oaicite:19]{index=19}
        if self.valid_to and self.valid_from and self.valid_from > self.valid_to:
            raise ValidationError("Validity stop date must be after the start date.")

        # Skill must belong to type; level must belong to type. :contentReference[oaicite:20]{index=20}
        if self.skill_id and self.skill_type_id and self.skill.skill_type_id_id != self.skill_type_id:
            raise ValidationError("Selected skill does not match skill type.")
        if self.skill_level_id and self.skill_type_id and self.skill_level.skill_type_id_id != self.skill_type_id:
            raise ValidationError("Selected level is not valid for this skill type.")

        # Overlap rules:
        # Regular skills → only one active per (linked, skill); certifications may coexist if date ranges differ. :contentReference[oaicite:21]{index=21}
        linked_name = self._linked_field_name()
        linked_value = getattr(self, linked_name + "_id", None)
        if not linked_value or not self.skill_id:
            return

        qs = self.__class__.objects.filter(**{linked_name: linked_value, "skill": self.skill}).exclude(pk=self.pk)

        if not self.is_certification:
            # For regular skills, deny another active skill for the same (linked, skill) where ranges overlap or are open-ended. :contentReference[oaicite:22]{index=22}
            if self.valid_to:
                overlap = qs.filter(models.Q(valid_to__isnull=True) | models.Q(valid_to__gte=self.valid_from),
                                    valid_from__lte=self.valid_to).exists()
            else:
                overlap = qs.filter(models.Q(valid_to__isnull=True) | models.Q(valid_to__gte=self.valid_from)).exists()
            if overlap:
                raise ValidationError("Only one active skill per skill is allowed for the same individual.")
        else:
            # Certifications may coexist but must not be identical tuples (level, from, to). :contentReference[oaicite:23]{index=23}
            same = qs.filter(skill_level=self.skill_level, valid_from=self.valid_from, valid_to=self.valid_to).exists()
            if same:
                raise ValidationError("Duplicate certification with the same level and validity window is not allowed.")

    # Odoo adds versioning commands for write/create to preserve history; in Django,
    # trigger this behavior at the service layer (views/serializers) when changing core fields. :contentReference[oaicite:24]{index=24}

    def _linked_field_name(self) -> str:
        """Child classes must return the name of the FK linking the individual (e.g. 'employee')."""
        raise NotImplementedError()
