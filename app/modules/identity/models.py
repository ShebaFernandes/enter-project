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
