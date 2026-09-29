import uuid

from django.db import models


class Notification(models.Model):
    class Channel(models.TextChoices):
        EMAIL = "EMAIL"
        WHATSAPP = "WHATSAPP"

    class State(models.TextChoices):
        QUEUED = "QUEUED"
        SENDING = "SENDING"
        SENT = "SENT"
        FAILED = "FAILED"
        CANCELLED = "CANCELLED"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant_id = models.UUIDField(null=True)
    candidate_profile_id = models.UUIDField(null=True)
    application_id = models.UUIDField(null=True)
    channel = models.CharField(max_length=20, choices=Channel)
    template_key = models.CharField(max_length=160)
    template_version = models.CharField(max_length=40)
    destination_ciphertext = models.BinaryField()
    consent_basis = models.CharField(max_length=120)
    state = models.CharField(max_length=20, choices=State, default=State.QUEUED)
    provider_reference = models.CharField(max_length=255, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    first_attempt_at = models.DateTimeField(null=True)
    next_attempt_at = models.DateTimeField(null=True)
    terminal_error_category = models.CharField(max_length=80, blank=True)
    idempotency_key = models.CharField(max_length=200, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=("state", "next_attempt_at", "created_at"))]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(attempts__lte=5),
                name="notification_attempts_max_5",
            )
        ]

    @property
    def candidate_state(self) -> str:
        if self.state in {self.State.QUEUED, self.State.SENDING}:
            return "PENDING"
        return self.state


class NotificationDeadLetter(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    notification = models.OneToOneField(Notification, on_delete=models.PROTECT)
    failure_category = models.CharField(max_length=80)
    failed_at = models.DateTimeField(auto_now_add=True)
    redriven_at = models.DateTimeField(null=True)
    redriven_by_id = models.UUIDField(null=True)
