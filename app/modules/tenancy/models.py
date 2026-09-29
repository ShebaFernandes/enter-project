import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower


class Tenant(models.Model):
    class Status(models.TextChoices):
        PROVISIONING = "PROVISIONING"
        ACTIVE = "ACTIVE"
        SUSPENDED = "SUSPENDED"
        CLOSED = "CLOSED"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=300)
    slug = models.SlugField(max_length=160)
    legal_boundary_reference = models.CharField(max_length=300)
    status = models.CharField(max_length=20, choices=Status, default=Status.PROVISIONING)
    default_timezone = models.CharField(max_length=64, default="Asia/Kolkata")
    retention_policy_version = models.CharField(max_length=80, default="launch-v1")
    version = models.PositiveBigIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                Lower("slug"),
                condition=~models.Q(status="CLOSED"),
                name="uniq_active_tenant_slug",
            )
        ]


class BusinessUnit(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE"
        INACTIVE = "INACTIVE"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, related_name="business_units")
    name = models.CharField(max_length=300)
    description = models.TextField(blank=True, max_length=2000)
    status = models.CharField(max_length=20, choices=Status, default=Status.ACTIVE)
    version = models.PositiveBigIntegerField(default=1)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                "tenant",
                Lower("name"),
                condition=models.Q(status="ACTIVE"),
                name="uniq_active_business_unit_name",
            )
        ]


class TenantMembership(models.Model):
    class Role(models.TextChoices):
        RECRUITER = "RECRUITER"
        HIRING_MANAGER = "HIRING_MANAGER"
        TENANT_ADMIN = "TENANT_ADMIN"

    class Status(models.TextChoices):
        INVITED = "INVITED"
        ACTIVE = "ACTIVE"
        SUSPENDED = "SUSPENDED"
        REVOKED = "REVOKED"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, related_name="memberships")
    identity = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="tenant_memberships"
    )
    role = models.CharField(max_length=30, choices=Role)
    status = models.CharField(max_length=20, choices=Status, default=Status.INVITED)
    scope = models.JSONField(default=dict)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "identity"], name="uniq_tenant_identity_membership"
            )
        ]

    def clean(self):
        allowed = {"opening_ids", "business_unit_ids"}
        if set(self.scope) - allowed:
            raise ValidationError({"scope": "Unsupported membership scope."})
        if any(not isinstance(value, list) for value in self.scope.values()):
            raise ValidationError({"scope": "Membership scopes must be identifier lists."})


class AccessGrant(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE"
        EXPIRED = "EXPIRED"
        REVOKED = "REVOKED"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, null=True)
    grantee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    purpose_code = models.CharField(max_length=100)
    field_scope = models.JSONField(default=list)
    object_scope = models.JSONField(default=dict)
    valid_from = models.DateTimeField()
    expires_at = models.DateTimeField()
    status = models.CharField(max_length=20, choices=Status, default=Status.ACTIVE)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        indexes = [models.Index(fields=("tenant", "grantee", "status", "expires_at"))]

    def clean(self):
        if not self.purpose_code.strip():
            raise ValidationError({"purpose_code": "Purpose is required."})
        if not self.field_scope or any(not str(field).strip() for field in self.field_scope):
            raise ValidationError({"field_scope": "At least one field is required."})
        if not self.object_scope.get("ids"):
            raise ValidationError({"object_scope": "At least one object is required."})
        if self.expires_at <= self.valid_from:
            raise ValidationError({"expires_at": "Expiry must follow activation."})


class EmergencyAccessRequest(models.Model):
    class Status(models.TextChoices):
        REQUESTED = "REQUESTED"
        APPROVED = "APPROVED"
        ACTIVE = "ACTIVE"
        REJECTED = "REJECTED"
        EXPIRED = "EXPIRED"
        REVOKED = "REVOKED"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="emergency_requests"
    )
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT)
    reason_code = models.CharField(max_length=100)
    reason = models.TextField(max_length=2000)
    incident_reference = models.CharField(max_length=200)
    object_scope = models.JSONField(default=dict)
    field_scope = models.JSONField(default=list)
    operation_scope = models.JSONField(default=list)
    requested_minutes = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=20, choices=Status, default=Status.REQUESTED)
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="emergency_approvals",
        null=True,
        blank=True,
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="emergency_revocations",
        null=True,
        blank=True,
    )
    revoked_at = models.DateTimeField(null=True, blank=True)
    tenant_admin_notified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        if not self.field_scope:
            raise ValidationError({"field_scope": "At least one field is required."})
        if not self.object_scope.get("ids"):
            raise ValidationError({"object_scope": "At least one object is required."})
        if self.operation_scope != ["READ"]:
            raise ValidationError({"operation_scope": "Emergency access is read-only."})
        if not self.reason_code.strip() or not self.reason.strip():
            raise ValidationError({"reason": "A reason code and justification are required."})
        if not self.incident_reference.strip():
            raise ValidationError({"incident_reference": "An incident reference is required."})
        if not 1 <= self.requested_minutes <= 60:
            raise ValidationError({"requested_minutes": "Must be between 1 and 60."})
        if self.approver_id and self.approver_id == self.requester_id:
            raise ValidationError({"approver": "Requester cannot self-approve."})
