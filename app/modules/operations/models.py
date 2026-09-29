import uuid

from django.db import models


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
