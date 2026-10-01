import uuid

from django.conf import settings
from django.db import models


class SearchWorkflowHandoff(models.Model):
    """Typed transitional transport, never arbitrary client/session JSON."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.CASCADE)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    credential = models.ForeignKey("identity.SessionCredential", on_delete=models.CASCADE)
    kind = models.CharField(
        max_length=20,
        choices=[
            ("criteria-review", "Criteria review"),
            ("search-results", "Search results"),
            ("comparison-selection", "Comparison selection"),
        ],
    )
    token_hash = models.CharField(max_length=64, unique=True)
    retry_hash = models.CharField(max_length=64)
    request_hash = models.CharField(max_length=64)
    payload_ciphertext = models.BinaryField()
    resource_version = models.CharField(max_length=64)
    workflow = models.ForeignKey("operations.WorkflowRun", null=True, on_delete=models.CASCADE)
    search = models.ForeignKey("search.SearchDefinition", null=True, on_delete=models.CASCADE)
    state = models.CharField(
        max_length=12,
        default="ACTIVE",
        choices=[("ACTIVE", "Active"), ("REVOKED", "Revoked"), ("COMPLETED", "Completed")],
    )
    version = models.PositiveBigIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(db_index=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["credential", "retry_hash"], name="uniq_handoff_retry")
        ]
