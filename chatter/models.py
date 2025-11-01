# chatter/models.py

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

# نفترض توفر Company و Employee ضمن مشروعك
COMPANY_MODEL = "base.Company"
EMPLOYEE_MODEL = "hr.Employee"


def _get_target_company_id(obj) -> int | None:
    """
    يحاول استخراج company_id من السجل الهدف إن وُجد.
    كل موديلاتك الأساسية لديها company أو company_id.
    """
    if not obj:
        return None
    # company_id خاصية مباشرة
    cid = getattr(obj, "company_id", None)
    if cid:
        return cid
    # أو عبر علاقة company
    comp = getattr(obj, "company", None)
    if comp is not None:
        return getattr(comp, "id", None)
    return None


class ChatterMessage(models.Model):
    """
    رسالة Chatter مرتبطة بأي سجل عبر GenericForeignKey.
    """
    company = models.ForeignKey(
        COMPANY_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="chatter_messages"
    )

    # الكاتب (User أساسي، وEmployee اختياري إن توفر)
    author_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="chatter_messages"
    )
    author_employee = models.ForeignKey(
        EMPLOYEE_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="chatter_messages"
    )

    body = models.TextField(_("Message body"))

    # الهدف العام (أي موديل)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, related_name="chatter_messages")
    object_id = models.PositiveIntegerField()
    target = GenericForeignKey("content_type", "object_id")

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "chatter_message"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["content_type", "object_id", "created_at"], name="chat_msg_ct_oid_dt_idx"),
            models.Index(fields=["company", "created_at"], name="chat_msg_comp_dt_idx"),
        ]
        permissions = [
            ("post_chatter_message", "Can post chatter message"),
            ("delete_own_chatter_message", "Can delete own chatter message"),
        ]
        constraints = [
            models.CheckConstraint(
                name="chat_msg_body_not_empty",
                check=~models.Q(body=""),
            ),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError
        super().clean()

        # ضمان وجود هدف/Body
        if not self.content_type_id or not self.object_id:
            raise ValidationError({"target": "Target record is required."})

        # اتساق الشركة: إن وُجدت شركة الهدف و/أو شركة الرسالة
        tgt_company_id = _get_target_company_id(self.target)
        if tgt_company_id:
            if self.company_id and self.company_id != tgt_company_id:
                raise ValidationError({"company": "Message company must match target company."})
            # اضبط الشركة تلقائيًا إن لم تُمرَّر
            if not self.company_id:
                self.company_id = tgt_company_id

        # لو مررت author_employee، تأكد أنه من نفس الشركة (إن عُرفت)
        if self.author_employee_id and self.company_id:
            if getattr(self.author_employee, "company_id", None) not in (None, self.company_id):
                raise ValidationError({"author_employee": "Author employee must belong to the same company."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"ChatterMessage<{self.id}> on {self.content_type}:{self.object_id}"


def chatter_attachment_upload_to(instance, filename: str) -> str:
    return f"chatter/{instance.message_id}/{filename}"


class ChatterAttachment(models.Model):
    """
    مرفق ملف لرسالة Chatter.
    """
    message = models.ForeignKey(ChatterMessage, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to=chatter_attachment_upload_to)
    filename = models.CharField(max_length=255, blank=True)
    mimetype = models.CharField(max_length=255, blank=True)
    size = models.BigIntegerField(null=True, blank=True)

    class Meta:
        db_table = "chatter_attachment"
        ordering = ("message_id", "id")
        indexes = [
            models.Index(fields=["message"], name="chat_att_msg_idx"),
        ]

    def save(self, *args, **kwargs):
        if self.file and (not self.filename):
            self.filename = getattr(self.file, "name", "") or ""
        if self.file and (not self.size):
            try:
                self.size = self.file.size
            except Exception:
                pass
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.filename or f"Attachment<{self.pk}>"


class ChatterFollower(models.Model):
    """
    متابع لسجل معيّن (User أو Employee). يمنع التكرار على نفس الهدف.
    """
    company = models.ForeignKey(
        COMPANY_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="chatter_followers"
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    employee = models.ForeignKey(EMPLOYEE_MODEL, on_delete=models.CASCADE, null=True, blank=True)

    # الهدف العام
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, related_name="chatter_followers")
    object_id = models.PositiveIntegerField()
    target = GenericForeignKey("content_type", "object_id")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "chatter_follower"
        ordering = ("content_type_id", "object_id", "id")
        indexes = [
            models.Index(fields=["content_type", "object_id"], name="chat_fol_ct_oid_idx"),
            models.Index(fields=["company"], name="chat_fol_company_idx"),
        ]
        constraints = [
            # لا تُقبل حالة بلا (user ولا employee)
            models.CheckConstraint(
                name="chat_fol_has_actor",
                check=models.Q(user__isnull=False) | models.Q(employee__isnull=False),
            ),
            # منع تكرار المتابع على نفس الهدف
            models.UniqueConstraint(
                fields=["content_type", "object_id", "user"],
                name="chat_fol_unique_user",
                condition=models.Q(user__isnull=False),
            ),
            models.UniqueConstraint(
                fields=["content_type", "object_id", "employee"],
                name="chat_fol_unique_employee",
                condition=models.Q(employee__isnull=False),
            ),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError
        super().clean()

        if not self.content_type_id or not self.object_id:
            raise ValidationError({"target": "Target record is required."})

        tgt_company_id = _get_target_company_id(self.target)
        if tgt_company_id:
            if self.company_id and self.company_id != tgt_company_id:
                raise ValidationError({"company": "Follower company must match target company."})
            if not self.company_id:
                self.company_id = tgt_company_id

        if self.employee_id and self.company_id:
            if getattr(self.employee, "company_id", None) not in (None, self.company_id):
                raise ValidationError({"employee": "Follower employee must belong to the same company."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        who = self.user_id or self.employee_id
        return f"Follower<{who}> on {self.content_type}:{self.object_id}"
