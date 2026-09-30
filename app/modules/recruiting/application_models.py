from __future__ import annotations

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from modules.tenancy.models import Tenant


class CandidateFacingStatus(models.TextChoices):
    APPLIED = "APPLIED"
    PROFILE_VIEWED = "PROFILE_VIEWED"
    SHORTLISTED = "SHORTLISTED"
    RECRUITER_INTERESTED = "RECRUITER_INTERESTED"
    INTERVIEW_REQUESTED = "INTERVIEW_REQUESTED"
    OFFER_MADE = "OFFER_MADE"
    NOT_SELECTED = "NOT_SELECTED"
    WITHDRAWN = "WITHDRAWN"


class InternalRecruitingStatus(models.TextChoices):
    SOURCED = "SOURCED"
    SHORTLISTED = "SHORTLISTED"
    CONTACTED = "CONTACTED"
    SCREENING = "SCREENING"
    INTERVIEWING = "INTERVIEWING"
    OFFERED = "OFFERED"
    REJECTED = "REJECTED"
    NOT_RELEVANT = "NOT_RELEVANT"
    HIRED = "HIRED"


class Application(models.Model):
    class State(models.TextChoices):
        DRAFT = "DRAFT"
        SUBMITTED = "SUBMITTED"
        ACTIVE = "ACTIVE"
        CLOSED = "CLOSED"
        WITHDRAWN = "WITHDRAWN"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, related_name="applications")
    opening = models.ForeignKey(
        "recruiting.Opening", on_delete=models.PROTECT, related_name="applications"
    )
    candidate_profile_id = models.UUIDField()
    candidate_work_record = models.ForeignKey(
        "recruiting.CandidateWorkRecord",
        db_column="candidate_work_record_id",
        on_delete=models.SET_NULL,
        related_name="linked_applications",
        null=True,
        blank=True,
    )
    resume = models.ForeignKey(
        "candidate.ResumeAsset",
        on_delete=models.PROTECT,
        related_name="applications",
        null=True,
        blank=True,
    )
    state = models.CharField(max_length=20, choices=State, default=State.DRAFT)
    internal_status = models.CharField(max_length=40, choices=InternalRecruitingStatus, blank=True)
    candidate_status = models.CharField(
        max_length=40, choices=CandidateFacingStatus, default=CandidateFacingStatus.APPLIED
    )
    suggested_candidate_status = models.CharField(  # noqa: DJ001 -- null means unmapped
        max_length=40, choices=CandidateFacingStatus, null=True, blank=True
    )
    answers = models.JSONField(default=dict)
    consent_context = models.ForeignKey(
        "candidate.ConsentRecord",
        db_column="consent_context_id",
        on_delete=models.SET_NULL,
        related_name="applications",
        null=True,
        blank=True,
    )
    notify_email = models.BooleanField(default=False)
    notify_whatsapp = models.BooleanField(default=False)
    status_published_at = models.DateTimeField(null=True, blank=True)
    status_published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="application_status_publications",
        null=True,
        blank=True,
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    withdrawn_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveBigIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "recruiting"
        constraints = [
            models.UniqueConstraint(
                fields=("opening", "candidate_profile_id"),
                name="uniq_opening_candidate_application",
            ),
            models.CheckConstraint(
                condition=models.Q(candidate_status__in=CandidateFacingStatus.values),
                name="application_candidate_status_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(suggested_candidate_status__isnull=True)
                | models.Q(suggested_candidate_status__in=CandidateFacingStatus.values),
                name="application_suggested_status_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(internal_status="")
                | models.Q(internal_status__in=InternalRecruitingStatus.values),
                name="application_internal_status_valid",
            ),
        ]
        indexes = [models.Index(fields=("tenant", "state", "updated_at"))]

    def clean(self):
        errors: dict[str, str] = {}
        if self.opening_id and self.tenant_id and self.opening.tenant_id != self.tenant_id:
            errors["opening"] = "Opening must belong to the application tenant."
        if self.resume_id and (
            self.resume is None or self.resume.profile_id != self.candidate_profile_id
        ):
            errors["resume"] = "Resume must belong to the candidate profile."
        if (
            self.state == self.State.WITHDRAWN
            and self.candidate_status != CandidateFacingStatus.WITHDRAWN
        ):
            errors["candidate_status"] = "Withdrawn applications must publish WITHDRAWN."
        if errors:
            raise ValidationError(errors)


class ApplicationStatusEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT)
    application = models.ForeignKey(Application, on_delete=models.PROTECT, related_name="history")
    prior_state = models.CharField(max_length=80, blank=True)
    new_state = models.CharField(max_length=80)
    suggested_candidate_status = models.CharField(  # noqa: DJ001 -- absence is distinct
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
        app_label = "recruiting"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(suggested_candidate_status__isnull=True)
                | models.Q(suggested_candidate_status__in=CandidateFacingStatus.values),
                name="status_event_suggestion_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(published_candidate_status__isnull=True)
                | models.Q(published_candidate_status__in=CandidateFacingStatus.values),
                name="status_event_publication_valid",
            ),
        ]
        indexes = [
            models.Index(fields=("tenant", "occurred_at"), name="recruiting__tenant__6abc97_idx")
        ]

    def clean(self):
        if self.application_id and self.tenant_id and self.application.tenant_id != self.tenant_id:
            raise ValidationError({"application": "Application history must remain tenant scoped."})


class ApplicationStatusPreview(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT)
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="previews")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    internal_status = models.CharField(max_length=40, choices=InternalRecruitingStatus)
    suggested_candidate_status = models.CharField(  # noqa: DJ001 -- null is contract-significant
        max_length=40, choices=CandidateFacingStatus, null=True, blank=True
    )
    application_version = models.PositiveBigIntegerField()
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "recruiting"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(internal_status__in=InternalRecruitingStatus.values),
                name="status_preview_internal_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(suggested_candidate_status__isnull=True)
                | models.Q(suggested_candidate_status__in=CandidateFacingStatus.values),
                name="status_preview_suggestion_valid",
            ),
        ]
        indexes = [models.Index(fields=("tenant", "application", "expires_at"))]

    @property
    def is_current(self) -> bool:
        return self.consumed_at is None and self.expires_at > timezone.now()
