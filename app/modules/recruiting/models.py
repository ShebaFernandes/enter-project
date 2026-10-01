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


class PublicOpeningProjection(models.Model):
    """Publication allowlist only; never an authorization or source-of-truth record."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True, max_length=20000)
    location = models.CharField(max_length=300, blank=True)
    work_mode = models.CharField(max_length=20, choices=Opening.WorkMode)
    employment_type = models.CharField(max_length=100)
    published_at = models.DateTimeField()
    closes_at = models.DateTimeField(null=True, blank=True)
    active = models.BooleanField(default=False)


class OpeningPublicationLink(models.Model):
    """Private linkage. Public readers have no privileges on this table."""

    opening = models.OneToOneField(Opening, primary_key=True, on_delete=models.CASCADE)
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT)


from .application_models import (  # noqa: E402,F401 - Django model discovery/re-export
    Application,
    ApplicationStatusEvent,
    ApplicationStatusPreview,
    CandidateFacingStatus,
    InternalRecruitingStatus,
)
from .work_models import (  # noqa: E402,F401 - Django model discovery/re-export
    CandidateWorkRecord,
    DisclosureRequest,
    RecruiterNote,
    RecruitingStatusEvent,
    ShortlistEntry,
)


class RecruiterEnteredCandidate(models.Model):
    SOURCE_TYPE = "RECRUITER_ENTERED_SYNTHETIC"
    SOURCE_LABEL = "Recruiter-entered synthetic record"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="recruiter_entered_candidates"
    )
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    display_name = models.CharField(max_length=200)
    location = models.JSONField(default=dict)
    experience_years = models.DecimalField(max_digits=6, decimal_places=2)
    skills = models.JSONField(default=list)
    source_type = models.CharField(max_length=40, default=SOURCE_TYPE, editable=False)
    source_label = models.CharField(max_length=80, default=SOURCE_LABEL, editable=False)
    version = models.PositiveBigIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(source_type="RECRUITER_ENTERED_SYNTHETIC"),
                name="recruiter_candidate_synthetic_source",
            ),
            models.CheckConstraint(
                condition=models.Q(experience_years__gte=0),
                name="recruiter_candidate_nonnegative_experience",
            ),
        ]
        indexes = [models.Index(fields=("tenant", "created_at"))]

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.source_type != self.SOURCE_TYPE or self.source_label != self.SOURCE_LABEL:
            raise ValidationError("Synthetic provenance is immutable.")
        if not self.skills or any(not str(skill).strip() for skill in self.skills):
            raise ValidationError({"skills": "At least one non-empty synthetic skill is required."})
