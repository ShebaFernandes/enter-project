import uuid

from django.conf import settings
from django.db import models

from modules.tenancy.models import BusinessUnit, Tenant


class Opening(models.Model):
    class WorkMode(models.TextChoices):
        REMOTE = "REMOTE"
        HYBRID = "HYBRID"
        ON_SITE = "ON_SITE"
        FLEXIBLE = "FLEXIBLE"

    class State(models.TextChoices):
        DRAFT = "DRAFT"
        OPEN = "OPEN"
        PAUSED = "PAUSED"
        CLOSED = "CLOSED"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, related_name="openings")
    business_unit = models.ForeignKey(
        BusinessUnit, on_delete=models.PROTECT, related_name="openings"
    )
    title = models.CharField(max_length=300)
    location = models.JSONField(default=dict)
    work_mode = models.CharField(max_length=20, choices=WorkMode)
    employment_type = models.CharField(max_length=100)
    description = models.TextField(blank=True, max_length=20000)
    state = models.CharField(max_length=20, choices=State, default=State.DRAFT)
    version = models.PositiveBigIntegerField(default=1)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="openings_created"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=("tenant", "state", "created_at"))]

    def clean(self):
        from django.core.exceptions import ValidationError

        if (
            self.business_unit_id
            and self.tenant_id
            and self.business_unit.tenant_id != self.tenant_id
        ):
            raise ValidationError(
                {"business_unit": "Business unit must belong to the opening tenant."}
            )


class HiringTeamMember(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    opening = models.ForeignKey(Opening, on_delete=models.CASCADE, related_name="hiring_team")
    membership = models.ForeignKey("tenancy.TenantMembership", on_delete=models.PROTECT)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="hiring_team_assignments"
    )
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("opening", "membership"), name="uniq_opening_hiring_member"
            )
        ]

    def clean(self):
        from django.core.exceptions import ValidationError

        if (
            self.opening_id
            and self.membership_id
            and self.opening.tenant_id != self.membership.tenant_id
        ):
            raise ValidationError(
                {"membership": "Hiring-team membership must belong to the opening tenant."}
            )
