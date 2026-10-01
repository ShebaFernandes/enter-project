import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


class AccessReview(models.Model):
    class ReviewType(models.TextChoices):
        MEMBERSHIP = "MEMBERSHIP"
        PRIVILEGED_ROLE = "PRIVILEGED_ROLE"
        PURPOSE_GRANT = "PURPOSE_GRANT"
        EMERGENCY_GRANT = "EMERGENCY_GRANT"
        AUDIT_ACCESS = "AUDIT_ACCESS"

    class State(models.TextChoices):
        PENDING = "PENDING"
        IN_PROGRESS = "IN_PROGRESS"
        COMPLETED = "COMPLETED"
        OVERDUE = "OVERDUE"

    class RemediationState(models.TextChoices):
        NOT_REQUIRED = "NOT_REQUIRED"
        PENDING = "PENDING"
        IN_PROGRESS = "IN_PROGRESS"
        COMPLETED = "COMPLETED"
        OVERDUE = "OVERDUE"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenancy.Tenant", on_delete=models.PROTECT, related_name="access_reviews"
    )
    review_type = models.CharField(max_length=30, choices=ReviewType)
    state = models.CharField(max_length=20, choices=State, default=State.PENDING)
    population_snapshot = models.JSONField(default=list)
    population_hash = models.CharField(max_length=64)
    due_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="assigned_access_reviews",
        null=True,
        blank=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_access_reviews",
    )
    decision_counts = models.JSONField(default=dict)
    findings = models.JSONField(default=list)
    revocations = models.JSONField(default=list)
    remediation_state = models.CharField(
        max_length=20,
        choices=RemediationState,
        default=RemediationState.NOT_REQUIRED,
    )
    version = models.PositiveBigIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=("tenant", "state", "due_at"))]
        constraints = [
            models.CheckConstraint(
                condition=Q(state="COMPLETED", completed_at__isnull=False) | ~Q(state="COMPLETED"),
                name="completed_access_review_has_time",
            )
        ]


class AccessReviewItem(models.Model):
    class Decision(models.TextChoices):
        PENDING = "PENDING"
        RETAIN = "RETAIN"
        REVOKE = "REVOKE"
        EXCEPTION = "EXCEPTION"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    review = models.ForeignKey(AccessReview, on_delete=models.CASCADE, related_name="items")
    assignment_type = models.CharField(max_length=30, choices=AccessReview.ReviewType)
    source_object_id = models.CharField(max_length=100)
    subject_id = models.UUIDField(null=True, blank=True)
    evidence = models.JSONField(default=dict)
    decision = models.CharField(max_length=20, choices=Decision, default=Decision.PENDING)
    finding = models.CharField(max_length=500, blank=True)
    exception_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="owned_access_review_exceptions",
        null=True,
        blank=True,
    )
    exception_expires_at = models.DateTimeField(null=True, blank=True)
    remediation_state = models.CharField(
        max_length=20,
        choices=AccessReview.RemediationState,
        default=AccessReview.RemediationState.NOT_REQUIRED,
    )
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("review", "source_object_id"),
                name="uniq_review_assignment",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        decision="EXCEPTION",
                        exception_owner__isnull=False,
                        exception_expires_at__isnull=False,
                    )
                    | ~Q(decision="EXCEPTION")
                ),
                name="review_exception_is_bounded",
            ),
        ]
        indexes = [models.Index(fields=("review", "decision", "remediation_state"))]
