import uuid

from django.conf import settings
from django.db import models


class AbuseOverride(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subject_token = models.CharField(max_length=64)
    action = models.CharField(max_length=40)
    reason_code = models.CharField(max_length=100)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    valid_from = models.DateTimeField()
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=("subject_token", "action", "expires_at"))]
