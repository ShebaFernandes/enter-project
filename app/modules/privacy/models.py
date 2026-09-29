from __future__ import annotations

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from modules.candidate.models import CandidateProfile
from modules.recruiting.models import Application


class DataRightsRequest(models.Model):
    class RequestType(models.TextChoices):
        ACCESS = "ACCESS"
        CORRECTION = "CORRECTION"
        WITHDRAW_CONSENT = "WITHDRAW_CONSENT"
        HIDE_PROFILE = "HIDE_PROFILE"
        EXPORT = "EXPORT"
        DELETE = "DELETE"

    class State(models.TextChoices):
        PENDING = "PENDING"
        IN_PROGRESS = "IN_PROGRESS"
        HELD = "HELD"
        COMPLETED = "COMPLETED"
        FAILED = "FAILED"
        CANCELLED = "CANCELLED"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(
        CandidateProfile, on_delete=models.PROTECT, related_name="rights_requests"
    )
    request_type = models.CharField(max_length=30, choices=RequestType)
    state = models.CharField(max_length=20, choices=State, default=State.PENDING)
    scope = models.JSONField(default=dict)
    correction = models.JSONField(default=dict)
    step_up_evidence_id = models.UUIDField(null=True, blank=True)
    consequence_confirmed_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    expected_completion_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)
    safe_detail = models.CharField(max_length=500, blank=True)
    support_escalated_at = models.DateTimeField(null=True, blank=True)
    failure_category = models.CharField(max_length=100, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        indexes = [models.Index(fields=("profile", "state", "submitted_at"))]


class RightsExport(models.Model):
    class State(models.TextChoices):
        PENDING = "PENDING"
        GENERATING = "GENERATING"
        READY = "READY"
        FAILED = "FAILED"
        EXPIRED = "EXPIRED"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.OneToOneField(
        DataRightsRequest, on_delete=models.PROTECT, related_name="export"
    )
    state = models.CharField(max_length=20, choices=State, default=State.PENDING)
    object_key = models.CharField(max_length=500, blank=True)
    payload_ciphertext = models.BinaryField(null=True, blank=True)
    content_manifest = models.JSONField(default=dict)
    content_hash = models.CharField(max_length=64, blank=True)
    ready_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    download_count = models.PositiveIntegerField(default=0)
    deleted_at = models.DateTimeField(null=True, blank=True)
    failure_category = models.CharField(max_length=100, blank=True)


class ActiveProcessRetentionException(models.Model):
    class State(models.TextChoices):
        ACTIVE = "ACTIVE"
        UNDER_REVIEW = "UNDER_REVIEW"
        RESOLVED = "RESOLVED"
        REVOKED = "REVOKED"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    version = models.PositiveBigIntegerField(default=1)
    profile = models.ForeignKey(
        CandidateProfile, on_delete=models.PROTECT, related_name="retention_exceptions"
    )
    application = models.ForeignKey(
        Application, on_delete=models.PROTECT, related_name="retention_exceptions"
    )
    policy_version = models.CharField(max_length=50)
    legal_basis = models.CharField(max_length=200)
    retained_data_scope = models.JSONField(default=list)
    lifecycle_state = models.CharField(max_length=20, choices=State, default=State.ACTIVE)
    start_date = models.DateTimeField()
    review_date = models.DateTimeField()
    terminating_event = models.CharField(max_length=200)
    resolution_date = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    audit_references = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=("profile", "lifecycle_state", "review_date"))]

    def clean(self):
        errors = {}
        if self.application_id and self.profile_id:
            if self.application.candidate_profile_id != self.profile_id:
                errors["application"] = "Application must belong to the candidate profile."
        if not self.retained_data_scope:
            errors["retained_data_scope"] = "A precise retained-data scope is required."
        if not self.audit_references:
            errors["audit_references"] = "At least one audit reference is required."
        if self.review_date and self.start_date and self.review_date <= self.start_date:
            errors["review_date"] = "Review must follow the exception start."
        if errors:
            raise ValidationError(errors)


class LegalHold(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(
        CandidateProfile, on_delete=models.PROTECT, related_name="legal_holds"
    )
    scope = models.JSONField(default=list)
    authority_reference = models.CharField(max_length=200)
    approver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    encrypted_rationale = models.BinaryField()
    starts_at = models.DateTimeField()
    review_at = models.DateTimeField()
    ends_at = models.DateTimeField(null=True, blank=True)


class DeletionLedger(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subject_token = models.BinaryField(unique=True)
    deletion_scope = models.JSONField(default=list)
    source_completion = models.JSONField(default=dict)
    backup_cutoff = models.DateTimeField()
    replay_status = models.CharField(max_length=30, default="PENDING")
    completed_at = models.DateTimeField(null=True, blank=True)
    evidence_hash = models.CharField(max_length=64, blank=True)


class RightsEscalation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.ForeignKey(
        DataRightsRequest, on_delete=models.PROTECT, related_name="escalations"
    )
    reason_ciphertext = models.BinaryField()
    created_at = models.DateTimeField(auto_now_add=True)
