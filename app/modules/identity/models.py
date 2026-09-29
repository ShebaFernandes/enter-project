import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models


class IdentityManager(BaseUserManager["Identity"]):
    def create_user(self, cognito_subject: str, **extra_fields):
        if not cognito_subject:
            raise ValueError("cognito_subject is required")
        user = self.model(cognito_subject=cognito_subject, **extra_fields)
        user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, cognito_subject: str, **extra_fields):
        extra_fields.update({"is_staff": True, "is_superuser": True})
        return self.create_user(cognito_subject, **extra_fields)


class Identity(AbstractBaseUser, PermissionsMixin):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE"
        SUSPENDED = "SUSPENDED"
        CLOSED = "CLOSED"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cognito_subject = models.CharField(max_length=255, unique=True, editable=False)
    email_lookup_hmac = models.BinaryField(unique=True, editable=False)
    email_ciphertext = models.BinaryField(editable=False)
    email_verified_at = models.DateTimeField(null=True)
    status = models.CharField(max_length=20, choices=Status, default=Status.ACTIVE)
    last_authenticated_at = models.DateTimeField(null=True)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    objects = IdentityManager()
    USERNAME_FIELD = "cognito_subject"


class IdentityCapability(models.Model):
    class Role(models.TextChoices):
        CANDIDATE = "CANDIDATE"
        PLATFORM_SECURITY_ADMIN = "PLATFORM_SECURITY_ADMIN"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    identity = models.ForeignKey(Identity, on_delete=models.CASCADE, related_name="capabilities")
    role = models.CharField(max_length=40, choices=Role)
    assigned_by = models.ForeignKey(
        Identity, on_delete=models.PROTECT, related_name="capabilities_assigned"
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["identity", "role"],
                condition=models.Q(revoked_at__isnull=True),
                name="uniq_active_global_capability",
            )
        ]


class SessionCredential(models.Model):
    class Assurance(models.TextChoices):
        VERIFIED_EMAIL_OTP = "VERIFIED_EMAIL_OTP"
        WORKFORCE_MFA = "WORKFORCE_MFA"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    identity = models.ForeignKey(Identity, on_delete=models.CASCADE, related_name="sessions")
    session_key_hash = models.BinaryField(unique=True, editable=False)
    provider_session_id = models.CharField(max_length=255, blank=True, editable=False)
    provider = models.CharField(max_length=80, editable=False)
    assurance = models.CharField(max_length=40, choices=Assurance, editable=False)
    refresh_token_ciphertext = models.BinaryField(null=True, editable=False)
    authenticated_at = models.DateTimeField(editable=False)
    expires_at = models.DateTimeField(editable=False)
    revoked_at = models.DateTimeField(null=True, editable=False)
    revocation_reason = models.CharField(max_length=80, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, editable=False)

    class Meta:
        indexes = [models.Index(fields=("identity", "revoked_at", "expires_at"))]


class StepUpEvidence(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    identity = models.ForeignKey(Identity, on_delete=models.CASCADE, related_name="step_up_events")
    session_credential = models.ForeignKey(
        SessionCredential, on_delete=models.CASCADE, related_name="step_up_events"
    )
    purpose = models.CharField(max_length=100, editable=False)
    method = models.CharField(max_length=40, choices=SessionCredential.Assurance, editable=False)
    nonce_hash = models.BinaryField(unique=True, editable=False)
    verified_at = models.DateTimeField(editable=False)
    expires_at = models.DateTimeField(editable=False)
    revoked_at = models.DateTimeField(null=True, editable=False)

    class Meta:
        indexes = [models.Index(fields=("identity", "purpose", "expires_at"))]
