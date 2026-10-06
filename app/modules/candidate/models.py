from __future__ import annotations

import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class CandidateProfile(models.Model):
    class State(models.TextChoices):
        DRAFT = "DRAFT"
        REVIEW_REQUIRED = "REVIEW_REQUIRED"
        PUBLISHED = "PUBLISHED"
        HIDDEN = "HIDDEN"
        DELETION_PENDING = "DELETION_PENDING"
        DELETED = "DELETED"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    identity = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="candidate_profile"
    )
    full_name_ciphertext = models.BinaryField(default=bytes)
    location = models.JSONField(default=dict, blank=True)
    headline = models.CharField(max_length=300, blank=True)
    current_role = models.CharField(max_length=200, blank=True)
    current_company = models.CharField(max_length=200, blank=True)
    experience_years = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    role_categories = models.JSONField(default=list, blank=True)
    preferred_locations = models.JSONField(default=list, blank=True)
    work_arrangements = models.JSONField(default=list, blank=True)
    education = models.JSONField(default=list, blank=True)
    meaningful_work = models.CharField(max_length=300, blank=True)
    notice_period = models.CharField(max_length=100, blank=True)
    availability_date = models.DateField(null=True, blank=True)
    compensation_ciphertext = models.BinaryField(null=True, blank=True)
    contact_preferences = models.JSONField(default=dict, blank=True)
    profile_state = models.CharField(max_length=30, choices=State, default=State.DRAFT)
    last_candidate_activity_at = models.DateTimeField(auto_now_add=True)
    consent_expires_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveBigIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(experience_years__gte=0), name="candidate_nonnegative_experience"
            )
        ]
        indexes = [models.Index(fields=("profile_state", "updated_at"))]


class CandidateSkill(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(CandidateProfile, on_delete=models.CASCADE, related_name="skills")
    normalized_name = models.CharField(max_length=200)
    display_name = models.CharField(max_length=200)
    provenance = models.CharField(max_length=30, default="CANDIDATE_REPORTED")
    review_state = models.CharField(max_length=20, default="ACCEPTED")
    ordering = models.PositiveSmallIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("profile", "normalized_name"), name="uniq_candidate_normalized_skill"
            )
        ]
        ordering = ("ordering", "display_name")


class CandidateContact(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(CandidateProfile, on_delete=models.CASCADE, related_name="contacts")
    channel = models.CharField(max_length=30)
    value_ciphertext = models.BinaryField()
    verified_at = models.DateTimeField(null=True, blank=True)
    purpose_scope = models.JSONField(default=list, blank=True)
    field_visibility = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("profile", "channel"), name="uniq_candidate_contact")
        ]


class ProfileLink(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(CandidateProfile, on_delete=models.CASCADE, related_name="links")
    normalized_url = models.URLField(max_length=500)
    display_label = models.CharField(max_length=100, blank=True)
    ordering = models.PositiveSmallIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("profile", "normalized_url"), name="uniq_profile_link")
        ]
        ordering = ("ordering", "normalized_url")


class EmploymentRecord(models.Model):
    class ValueState(models.TextChoices):
        CONFIRMED = "CONFIRMED"
        SUGGESTED = "SUGGESTED"
        AMBIGUOUS = "AMBIGUOUS"
        MISSING = "MISSING"

    class DatePrecision(models.TextChoices):
        DAY = "DAY"
        MONTH = "MONTH"
        YEAR = "YEAR"
        UNKNOWN = "UNKNOWN"

    class EmploymentType(models.TextChoices):
        PERMANENT = "PERMANENT"
        INTERNSHIP = "INTERNSHIP"
        APPRENTICESHIP = "APPRENTICESHIP"
        FIXED_TERM_CONTRACT = "FIXED_TERM_CONTRACT"
        CONSULTING = "CONSULTING"
        SEASONAL = "SEASONAL"
        OTHER_TEMPORARY = "OTHER_TEMPORARY"
        OTHER = "OTHER"
        UNKNOWN = "UNKNOWN"

    class Provenance(models.TextChoices):
        CANDIDATE_REPORTED = "CANDIDATE_REPORTED"
        RESUME_EXTRACTED = "RESUME_EXTRACTED"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(
        CandidateProfile, on_delete=models.CASCADE, related_name="employment_history"
    )
    company = models.CharField(max_length=300)
    role_title = models.CharField(max_length=300, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    start_date_state = models.CharField(max_length=20, choices=ValueState)
    end_date_state = models.CharField(max_length=20, choices=ValueState)
    start_date_precision = models.CharField(
        max_length=10, choices=DatePrecision, default=DatePrecision.UNKNOWN
    )
    end_date_precision = models.CharField(
        max_length=10, choices=DatePrecision, default=DatePrecision.UNKNOWN
    )
    is_current = models.BooleanField(default=False)
    employment_type = models.CharField(max_length=30, choices=EmploymentType)
    employment_type_state = models.CharField(max_length=20, choices=ValueState)
    provenance = models.CharField(max_length=30, choices=Provenance)
    confidence = models.DecimalField(max_digits=4, decimal_places=3, null=True, blank=True)
    source_spans = models.JSONField(default=list, blank=True)
    ordering = models.PositiveSmallIntegerField(default=0)
    version = models.PositiveBigIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("ordering", "created_at")
        constraints = [
            models.CheckConstraint(
                condition=Q(confidence__isnull=True) | Q(confidence__gte=0, confidence__lte=1),
                name="employment_confidence_range",
            ),
            models.CheckConstraint(
                condition=Q(is_current=False) | Q(end_date__isnull=True),
                name="current_employment_has_no_end_date",
            ),
            models.CheckConstraint(
                condition=Q(start_date_state__in=["AMBIGUOUS", "MISSING"])
                | Q(start_date__isnull=False),
                name="known_employment_start_has_value",
            ),
            models.CheckConstraint(
                condition=Q(end_date_state__in=["AMBIGUOUS", "MISSING"])
                | Q(end_date__isnull=False),
                name="known_employment_end_has_value",
            ),
        ]

    def clean(self):
        errors: dict[str, str] = {}
        if not self.company.strip():
            errors["company"] = "Company is required."
        if self.is_current and self.end_date is not None:
            errors["end_date"] = "A current role cannot have an end date."
        if self.is_current and self.end_date_state == self.ValueState.CONFIRMED:
            errors["end_date_state"] = "A current role cannot have a confirmed end date."
        if self.start_date_state == self.ValueState.CONFIRMED and self.start_date is None:
            errors["start_date"] = "A confirmed start date requires a value."
        if self.end_date_state == self.ValueState.CONFIRMED and self.end_date is None:
            errors["end_date"] = "A confirmed end date requires a value."
        if self.start_date and self.end_date and self.end_date < self.start_date:
            errors["end_date"] = "End date cannot precede start date."
        if errors:
            raise ValidationError(errors)


class CandidateFinding(models.Model):
    class Result(models.TextChoices):
        FOUND = "FOUND"
        NOT_FOUND = "NOT_FOUND"
        INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
        EXCLUDED = "EXCLUDED"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(CandidateProfile, on_delete=models.CASCADE, related_name="findings")
    code = models.CharField(max_length=80)
    severity = models.CharField(max_length=30, default="INFORMATIONAL")
    result = models.CharField(max_length=30, choices=Result)
    source_record_type = models.CharField(max_length=80)
    source_record_id = models.UUIDField()
    source_record_version = models.PositiveBigIntegerField()
    evidence = models.JSONField(default=dict)
    message_key = models.CharField(max_length=120)
    calculation_version = models.CharField(max_length=100)
    evaluated_at = models.DateTimeField()
    superseded_at = models.DateTimeField(null=True, blank=True)
    audit_references = models.JSONField(default=list, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=(
                    "profile",
                    "code",
                    "source_record_type",
                    "source_record_id",
                    "calculation_version",
                ),
                condition=Q(superseded_at__isnull=True),
                name="uniq_active_candidate_finding_evaluation",
            ),
            models.CheckConstraint(
                condition=Q(severity="INFORMATIONAL"), name="candidate_finding_informational_only"
            ),
        ]
        indexes = [models.Index(fields=("profile", "code", "result", "superseded_at"))]


class ConsentRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(CandidateProfile, on_delete=models.CASCADE, related_name="consents")
    purpose = models.CharField(max_length=100)
    field_scope = models.JSONField(default=list)
    audience_scope = models.JSONField(default=dict)
    notice_version = models.CharField(max_length=50)
    affirmative_action = models.CharField(max_length=100)
    locale = models.CharField(max_length=20, default="en-IN")
    source_request_id = models.CharField(max_length=100)
    captured_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    withdrawn_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        indexes = [models.Index(fields=("profile", "purpose", "withdrawn_at"))]


class VisibilityRule(models.Model):
    class Mode(models.TextChoices):
        APPROVED_RECRUITERS = "APPROVED_RECRUITERS"
        MATCHING_ROLES = "MATCHING_ROLES"
        APPLIED_ROLES_ONLY = "APPLIED_ROLES_ONLY"
        NOT_LOOKING = "NOT_LOOKING"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(
        CandidateProfile, on_delete=models.CASCADE, related_name="visibility_rules"
    )
    mode = models.CharField(max_length=30, choices=Mode)
    approved_tenant_ids = models.JSONField(default=list, blank=True)
    matching_preferences = models.JSONField(default=dict, blank=True)
    consent_record = models.ForeignKey(ConsentRecord, on_delete=models.PROTECT)
    effective_at = models.DateTimeField(auto_now_add=True)
    superseded_at = models.DateTimeField(null=True, blank=True)
    policy_version = models.CharField(max_length=50, default="visibility-v1")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("profile",),
                condition=Q(superseded_at__isnull=True),
                name="uniq_current_visibility_rule",
            )
        ]

    def clean(self):
        errors = {}
        if self.mode == self.Mode.APPROVED_RECRUITERS and not self.approved_tenant_ids:
            errors["approved_tenant_ids"] = "At least one approved tenant is required."
        if self.mode == self.Mode.MATCHING_ROLES and not self.matching_preferences:
            errors["matching_preferences"] = "Matching preferences are required."
        if self.consent_record_id and self.profile_id != self.consent_record.profile_id:
            errors["consent_record"] = "Consent must belong to the profile."
        if errors:
            raise ValidationError(errors)


class ResumeAsset(models.Model):
    class ScanStatus(models.TextChoices):
        UPLOADING = "UPLOADING"
        SCANNING = "SCANNING"
        CLEAN = "CLEAN"
        SCAN_FAILED = "SCAN_FAILED"
        REJECTED = "REJECTED"

    class ParseStatus(models.TextChoices):
        NOT_STARTED = "NOT_STARTED"
        PARSING = "PARSING"
        REVIEW_REQUIRED = "REVIEW_REQUIRED"
        READY = "READY"
        PARSE_FAILED = "PARSE_FAILED"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(CandidateProfile, on_delete=models.CASCADE, related_name="resumes")
    quarantine_key = models.CharField(max_length=500, unique=True)
    clean_key = models.CharField(max_length=500, blank=True)
    original_filename_ciphertext = models.BinaryField()
    declared_mime = models.CharField(max_length=150)
    detected_mime = models.CharField(max_length=150, blank=True)
    size_bytes = models.PositiveIntegerField()
    sha256 = models.CharField(max_length=64)
    scan_status = models.CharField(max_length=20, choices=ScanStatus, default=ScanStatus.UPLOADING)
    parse_status = models.CharField(
        max_length=30, choices=ParseStatus, default=ParseStatus.NOT_STARTED
    )
    scan_provider_ref = models.CharField(max_length=200, blank=True)
    is_current = models.BooleanField(default=True)
    retention_until = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveBigIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("profile",),
                condition=Q(is_current=True, deleted_at__isnull=True),
                name="uniq_current_candidate_resume",
            )
        ]


class ExtractedFact(models.Model):
    class State(models.TextChoices):
        SUGGESTED = "SUGGESTED"
        ACCEPTED = "ACCEPTED"
        CORRECTED = "CORRECTED"
        REJECTED = "REJECTED"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    resume = models.ForeignKey(ResumeAsset, on_delete=models.CASCADE, related_name="facts")
    fact_type = models.CharField(max_length=100)
    normalized_value = models.JSONField(null=True, blank=True)
    source_excerpt_ciphertext = models.BinaryField(null=True, blank=True)
    source_spans = models.JSONField(default=list, blank=True)
    confidence = models.DecimalField(max_digits=4, decimal_places=3, null=True, blank=True)
    extraction_method = models.CharField(max_length=100)
    model_version = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=20, choices=State, default=State.SUGGESTED)
    reviewed_at = models.DateTimeField(null=True, blank=True)


class ProfileEvidence(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(CandidateProfile, on_delete=models.CASCADE, related_name="evidence")
    fact_type = models.CharField(max_length=100)
    normalized_value = models.JSONField()
    provenance = models.CharField(max_length=40)
    source_id = models.UUIDField(null=True, blank=True)
    confidence = models.DecimalField(max_digits=4, decimal_places=3, null=True, blank=True)
    visibility_scope = models.JSONField(default=dict, blank=True)
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField(null=True, blank=True)
