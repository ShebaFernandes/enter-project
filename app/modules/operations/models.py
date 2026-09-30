import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


def workflow_review_expiry():
    return timezone.now() + timedelta(days=30)


class IdempotencyRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor_key = models.CharField(max_length=200)
    key = models.CharField(max_length=200)
    request_hash = models.CharField(max_length=64)
    response_status = models.PositiveSmallIntegerField(null=True)
    response_body = models.JSONField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["actor_key", "key"], name="uniq_idempotency_actor_key")
        ]


class OutboxEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    aggregate_type = models.CharField(max_length=100)
    aggregate_id = models.UUIDField()
    aggregate_version = models.PositiveBigIntegerField()
    event_type = models.CharField(max_length=200)
    tenant_id = models.UUIDField(null=True)
    actor_id = models.UUIDField(null=True)
    correlation_id = models.UUIDField(null=True)
    payload = models.JSONField(default=dict)
    idempotency_key = models.CharField(max_length=250, unique=True)
    occurred_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True)
    attempts = models.PositiveSmallIntegerField(default=0)


class ProcessedEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_id = models.UUIDField()
    consumer = models.CharField(max_length=120)
    processed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("event_id", "consumer"), name="uniq_processed_event_consumer"
            )
        ]


class WorkflowRun(models.Model):
    class Status(models.TextChoices):
        AWAITING_REVIEW = "AWAITING_REVIEW"
        COMPLETED = "COMPLETED"
        FAILED = "FAILED"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workflow_type = models.CharField(max_length=100)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=Status)
    current_step = models.CharField(max_length=100)
    input_hash = models.CharField(max_length=64)
    model_version = models.CharField(max_length=200, blank=True)
    prompt_version = models.CharField(max_length=100)
    checkpoint_ciphertext = models.BinaryField()
    expires_at = models.DateTimeField(default=workflow_review_expiry)
    last_error_category = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(expires_at__gt=models.F("created_at")),
                name="workflow_expiry_after_creation",
            )
        ]
        indexes = [
            models.Index(
                fields=("tenant", "actor", "status", "expires_at"),
                name="operations__tenant__ea8233_idx",
            )
        ]
