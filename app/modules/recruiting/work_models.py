from __future__ import annotations

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from modules.operations.crypto import decrypt, encrypt

from .application_models import Application, InternalRecruitingStatus


class CandidateWorkRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenancy.Tenant", on_delete=models.CASCADE, related_name="candidate_work_records"
    )
    candidate_profile = models.ForeignKey(
        "candidate.CandidateProfile", on_delete=models.CASCADE, related_name="recruiter_work"
    )
    originating_search = models.ForeignKey(
        "search.SearchDefinition", on_delete=models.PROTECT, related_name="candidate_work_records"
    )
    opening = models.ForeignKey(
        "recruiting.Opening",
        on_delete=models.PROTECT,
        related_name="candidate_work_records",
        null=True,
        blank=True,
    )
    internal_status = models.CharField(
        max_length=40, choices=InternalRecruitingStatus, default=InternalRecruitingStatus.SOURCED
    )
    shortlisted = models.BooleanField(default=False)
    shortlist_order = models.PositiveIntegerField(null=True, blank=True)
    structured_reasons = models.JSONField(default=list, blank=True)
    explanatory_note_ciphertext = models.BinaryField(null=True, blank=True)
    version = models.PositiveBigIntegerField(default=1)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="candidate_work_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="candidate_work_updated",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("tenant", "candidate_profile", "originating_search"),
                name="uniq_candidate_work_context",
            ),
            models.CheckConstraint(
                condition=Q(internal_status__in=InternalRecruitingStatus.values),
                name="candidate_work_internal_status_valid",
            ),
            models.CheckConstraint(
                condition=Q(shortlisted=True) | Q(shortlist_order__isnull=True),
                name="candidate_work_order_requires_shortlist",
            ),
        ]
        indexes = [
            models.Index(fields=("tenant", "opening", "internal_status")),
            models.Index(fields=("tenant", "candidate_profile", "updated_at")),
        ]

    def clean(self):
        errors: dict[str, str] = {}
        if self.originating_search_id and self.originating_search.tenant_id != self.tenant_id:
            errors["originating_search"] = "Search must belong to the candidate-work tenant."
        if (
            self.opening_id
            and self.opening is not None
            and self.opening.tenant_id != self.tenant_id
        ):
            errors["opening"] = "Opening must belong to the candidate-work tenant."
        if self.internal_status == InternalRecruitingStatus.NOT_RELEVANT and not (
            self.structured_reasons or self.explanatory_note_ciphertext
        ):
            errors["structured_reasons"] = "Not relevant requires a reason or explanatory note."
        if errors:
            raise ValidationError(errors)

    @property
    def explanatory_note(self) -> str:
        return (
            decrypt(bytes(self.explanatory_note_ciphertext))
            if self.explanatory_note_ciphertext
            else ""
        )

    def set_explanatory_note(self, value: str | None) -> None:
        self.explanatory_note_ciphertext = (
            encrypt(value.strip()) if value and value.strip() else None
        )


class RecruiterNote(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.CASCADE)
    candidate_work = models.ForeignKey(
        CandidateWorkRecord,
        on_delete=models.CASCADE,
        related_name="notes",
        null=True,
        blank=True,
    )
    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name="recruiter_notes",
        null=True,
        blank=True,
    )
    body_ciphertext = models.BinaryField()
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    hiring_team_visible = models.BooleanField(default=False)
    version = models.PositiveBigIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(candidate_work__isnull=False, application__isnull=True)
                    | Q(candidate_work__isnull=True, application__isnull=False)
                ),
                name="recruiter_note_exactly_one_owner",
            )
        ]
        indexes = [models.Index(fields=("tenant", "created_at"))]

    def clean(self):
        owner = self.candidate_work or self.application
        if owner is None or owner.tenant_id != self.tenant_id:
            raise ValidationError("Note owner must belong to the note tenant.")

    @property
    def body(self) -> str:
        return decrypt(bytes(self.body_ciphertext))

    def set_body(self, value: str) -> None:
        body = value.strip()
        if not body:
            raise ValidationError({"body": "Note body is required."})
        if len(body) > 5000:
            raise ValidationError({"body": "Note body must be at most 5000 characters."})
        self.body_ciphertext = encrypt(body)


class ShortlistEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.CASCADE)
    candidate_work = models.OneToOneField(
        CandidateWorkRecord,
        on_delete=models.CASCADE,
        related_name="shortlist_entry",
        null=True,
        blank=True,
    )
    application = models.OneToOneField(
        Application,
        on_delete=models.CASCADE,
        related_name="shortlist_entry",
        null=True,
        blank=True,
    )
    selected = models.BooleanField(default=True)
    ordering = models.PositiveIntegerField(default=0)
    selected_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    version = models.PositiveBigIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(candidate_work__isnull=False, application__isnull=True)
                    | Q(candidate_work__isnull=True, application__isnull=False)
                ),
                name="shortlist_entry_exactly_one_owner",
            )
        ]


class RecruitingStatusEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.CASCADE)
    candidate_work = models.ForeignKey(
        CandidateWorkRecord,
        on_delete=models.CASCADE,
        related_name="status_history",
        null=True,
        blank=True,
    )
    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name="internal_status_history",
        null=True,
        blank=True,
    )
    prior_status = models.CharField(max_length=40, blank=True)
    new_status = models.CharField(max_length=40, choices=InternalRecruitingStatus)
    structured_reasons = models.JSONField(default=list, blank=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    idempotency_key = models.CharField(max_length=200, unique=True)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(candidate_work__isnull=False, application__isnull=True)
                    | Q(candidate_work__isnull=True, application__isnull=False)
                ),
                name="status_event_exactly_one_owner",
            )
        ]


class DisclosureRequest(models.Model):
    class ContextType(models.TextChoices):
        APPLICATION = "APPLICATION"
        CANDIDATE_WORK = "CANDIDATE_WORK"

    class State(models.TextChoices):
        PREVIEWED = "PREVIEWED"
        PENDING = "PENDING"
        SUCCEEDED = "SUCCEEDED"
        FAILED = "FAILED"
        CANCELLED = "CANCELLED"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.CASCADE)
    candidate_profile = models.ForeignKey(
        "candidate.CandidateProfile", on_delete=models.CASCADE, related_name="disclosures"
    )
    application = models.ForeignKey(
        Application,
        on_delete=models.PROTECT,
        related_name="disclosures",
        null=True,
        blank=True,
    )
    candidate_work = models.ForeignKey(
        CandidateWorkRecord,
        on_delete=models.PROTECT,
        related_name="disclosures",
        null=True,
        blank=True,
    )
    purpose = models.CharField(max_length=200)
    destination_type = models.CharField(max_length=40)
    destination_identifier_ciphertext = models.BinaryField()
    destination_preview = models.CharField(max_length=200)
    requested_fields = models.JSONField(default=list, blank=True)
    permitted_fields = models.JSONField(default=list, blank=True)
    excluded_fields = models.JSONField(default=list, blank=True)
    consent_record = models.ForeignKey("candidate.ConsentRecord", on_delete=models.PROTECT)
    preview_hash = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="confirmed_disclosures",
        null=True,
        blank=True,
    )
    state = models.CharField(max_length=20, choices=State, default=State.PREVIEWED)
    result_category = models.CharField(max_length=80, blank=True)
    idempotency_key = models.CharField(max_length=200, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(candidate_work__isnull=False, application__isnull=True)
                    | Q(candidate_work__isnull=True, application__isnull=False)
                ),
                name="disclosure_exactly_one_context",
            )
        ]
        indexes = [models.Index(fields=("tenant", "candidate_profile", "created_at"))]

    def clean(self):
        context = self.candidate_work or self.application
        if context is None or context.tenant_id != self.tenant_id:
            raise ValidationError("Disclosure context must belong to the active tenant.")
        if context.candidate_profile_id != self.candidate_profile_id:
            raise ValidationError("Disclosure candidate must match its context.")
