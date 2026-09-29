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


class CandidateFacingStatus(models.TextChoices):
    APPLIED = "APPLIED"
    PROFILE_VIEWED = "PROFILE_VIEWED"
    SHORTLISTED = "SHORTLISTED"
    RECRUITER_INTERESTED = "RECRUITER_INTERESTED"
    INTERVIEW_REQUESTED = "INTERVIEW_REQUESTED"
    OFFER_MADE = "OFFER_MADE"
    NOT_SELECTED = "NOT_SELECTED"
    WITHDRAWN = "WITHDRAWN"


class Application(models.Model):
    """Foundation-only application aggregate shell; no submission workflow is enabled."""

    class State(models.TextChoices):
        DRAFT = "DRAFT"
        SUBMITTED = "SUBMITTED"
        ACTIVE = "ACTIVE"
        CLOSED = "CLOSED"
        WITHDRAWN = "WITHDRAWN"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, related_name="applications")
    opening = models.ForeignKey(Opening, on_delete=models.PROTECT, related_name="applications")
    candidate_profile_id = models.UUIDField()
    state = models.CharField(max_length=20, choices=State, default=State.DRAFT)
    candidate_status = models.CharField(
        max_length=40, choices=CandidateFacingStatus, default=CandidateFacingStatus.APPLIED
    )
    suggested_candidate_status = models.CharField(  # noqa: DJ001 -- contract requires null
        max_length=40, choices=CandidateFacingStatus, null=True, blank=True
    )
    answers = models.JSONField(default=dict)
    consent_context_id = models.UUIDField(null=True)
    submitted_at = models.DateTimeField(null=True)
    withdrawn_at = models.DateTimeField(null=True)
    closed_at = models.DateTimeField(null=True)
    version = models.PositiveBigIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("opening", "candidate_profile_id"),
                name="uniq_opening_candidate_application",
            ),
        ]
        indexes = [models.Index(fields=("tenant", "state", "updated_at"))]

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.opening_id and self.tenant_id and self.opening.tenant_id != self.tenant_id:
            raise ValidationError({"opening": "Opening must belong to the application tenant."})


class ApplicationStatusEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT)
    application = models.ForeignKey(Application, on_delete=models.PROTECT, related_name="history")
    prior_state = models.CharField(max_length=80, blank=True)
    new_state = models.CharField(max_length=80)
    suggested_candidate_status = models.CharField(  # noqa: DJ001 -- contract requires null
        max_length=40, choices=CandidateFacingStatus, null=True, blank=True
    )
    published_candidate_status = models.CharField(  # noqa: DJ001 -- absence is distinct
        max_length=40, choices=CandidateFacingStatus, null=True, blank=True
    )
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    reason_code = models.CharField(max_length=100, blank=True)
    idempotency_key = models.CharField(max_length=200, unique=True)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=("tenant", "occurred_at"), name="recruiting__tenant__6abc97_idx")
        ]

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.application_id and self.tenant_id and self.application.tenant_id != self.tenant_id:
            raise ValidationError({"application": "Application history must remain tenant scoped."})


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
