import uuid

from django.conf import settings
from django.db import models


class AuditEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    occurred_at = models.DateTimeField(auto_now_add=True, editable=False)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    tenant_id = models.UUIDField(null=True, editable=False)
    action = models.CharField(max_length=160, editable=False)
    target_type = models.CharField(max_length=100, editable=False)
    target_id = models.CharField(max_length=100, blank=True, editable=False)
    purpose_code = models.CharField(max_length=100, blank=True, editable=False)
    outcome = models.CharField(max_length=20, editable=False)
    metadata = models.JSONField(default=dict, editable=False)
    previous_hash = models.CharField(max_length=64, blank=True, editable=False)
    event_hash = models.CharField(max_length=64, unique=True, editable=False)

    class Meta:
        ordering = ("occurred_at", "id")
        indexes = [models.Index(fields=("tenant_id", "occurred_at"))]

    def save(self, *args, **kwargs):
        if self.pk and AuditEvent.objects.filter(pk=self.pk).exists():
            raise TypeError("Audit events are immutable")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise TypeError("Audit events are immutable")


class AuditCheckpoint(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    checkpoint_date = models.DateField(unique=True)
    terminal_hash = models.CharField(max_length=64)
    signature = models.BinaryField()
    object_key = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)
