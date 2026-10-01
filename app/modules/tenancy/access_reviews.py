from __future__ import annotations

import hashlib
import json
from collections import Counter

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from modules.operations.outbox import enqueue

from .audit import record_governance_event
from .grants import revoke_emergency_access
from .models import AccessGrant, EmergencyAccessRequest, TenantMembership
from .policy import AuthorizationRequest, authorize
from .review_models import AccessReview, AccessReviewItem


def _authorize(membership) -> None:
    authorize(
        AuthorizationRequest(
            action="access_review.manage",
            role=membership.role,
            tenant_id=membership.tenant_id,
            object_tenant_id=membership.tenant_id,
            actor=membership.identity,
        )
    )


def _membership_population(tenant_id, *, privileged_only: bool = False):
    queryset = TenantMembership.objects.filter(
        tenant_id=tenant_id,
        status__in=[TenantMembership.Status.ACTIVE, TenantMembership.Status.INVITED],
    )
    if privileged_only:
        queryset = queryset.filter(role=TenantMembership.Role.TENANT_ADMIN)
    return [
        {
            "source_object_id": str(item.id),
            "subject_id": item.identity_id,
            "evidence": {"role": item.role, "status": item.status, "version": item.version},
        }
        for item in queryset.order_by("id")
    ]


def _population(tenant_id, review_type: str):
    if review_type == AccessReview.ReviewType.MEMBERSHIP:
        return _membership_population(tenant_id)
    if review_type in {
        AccessReview.ReviewType.PRIVILEGED_ROLE,
        AccessReview.ReviewType.AUDIT_ACCESS,
    }:
        return _membership_population(tenant_id, privileged_only=True)
    if review_type == AccessReview.ReviewType.PURPOSE_GRANT:
        return [
            {
                "source_object_id": str(item.id),
                "subject_id": item.grantee_id,
                "evidence": {
                    "purpose_code": item.purpose_code,
                    "status": item.status,
                    "expires_at": item.expires_at.isoformat(),
                    "version": item.version,
                },
            }
            for item in AccessGrant.objects.filter(
                tenant_id=tenant_id, status=AccessGrant.Status.ACTIVE
            ).order_by("id")
        ]
    if review_type == AccessReview.ReviewType.EMERGENCY_GRANT:
        return [
            {
                "source_object_id": str(item.id),
                "subject_id": item.requester_id,
                "evidence": {
                    "status": item.status,
                    "expires_at": item.expires_at.isoformat() if item.expires_at else None,
                    "reason_code": item.reason_code,
                },
            }
            for item in EmergencyAccessRequest.objects.filter(tenant_id=tenant_id)
            .exclude(status__in=["EXPIRED", "REJECTED", "REVOKED"])
            .order_by("id")
        ]
    raise ValidationError({"review_type": "Unsupported access-review type."})


def _population_hash(population: list[dict]) -> str:
    return hashlib.sha256(
        json.dumps(population, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


@transaction.atomic
def create_access_review(*, membership, review_type: str, due_at, reviewer_id=None) -> AccessReview:
    _authorize(membership)
    if review_type not in AccessReview.ReviewType.values:
        raise ValidationError({"review_type": "Unsupported access-review type."})
    reviewer = None
    if reviewer_id:
        reviewer_membership = TenantMembership.objects.filter(
            tenant_id=membership.tenant_id,
            identity_id=reviewer_id,
            role=TenantMembership.Role.TENANT_ADMIN,
            status=TenantMembership.Status.ACTIVE,
        ).first()
        if reviewer_membership is None:
            raise PermissionDenied("Reviewer unavailable")
        reviewer = reviewer_membership.identity
    population = _population(membership.tenant_id, review_type)
    review = AccessReview.objects.create(
        tenant_id=membership.tenant_id,
        review_type=review_type,
        state=AccessReview.State.IN_PROGRESS,
        population_snapshot=[
            {
                "assignment_type": review_type,
                "source_object_id": item["source_object_id"],
                "subject_id": str(item["subject_id"]) if item["subject_id"] else None,
                "evidence": item["evidence"],
            }
            for item in population
        ],
        population_hash=_population_hash(population),
        due_at=due_at,
        reviewer=reviewer,
        created_by=membership.identity,
    )
    AccessReviewItem.objects.bulk_create(
        [
            AccessReviewItem(
                review=review,
                assignment_type=review_type,
                source_object_id=item["source_object_id"],
                subject_id=item["subject_id"],
                evidence=item["evidence"],
            )
            for item in population
        ]
    )
    record_governance_event(
        membership=membership,
        action="ACCESS_REVIEW_CREATE",
        target_type="access_review",
        target_id=review.id,
        review_type=review_type,
        population_count=len(population),
    )
    return review


@transaction.atomic
def populate_periodic_access_reviews(*, membership, due_at, reviewer_id=None) -> list[AccessReview]:
    """Snapshot each governed assignment class without duplicating an open review."""
    _authorize(membership)
    reviews: list[AccessReview] = []
    for review_type in AccessReview.ReviewType.values:
        if AccessReview.objects.filter(
            tenant_id=membership.tenant_id,
            review_type=review_type,
            state__in=[
                AccessReview.State.PENDING,
                AccessReview.State.IN_PROGRESS,
                AccessReview.State.OVERDUE,
            ],
        ).exists():
            continue
        review = create_access_review(
            membership=membership,
            review_type=review_type,
            due_at=due_at,
            reviewer_id=reviewer_id,
        )
        enqueue(
            aggregate_type="access_review",
            aggregate_id=review.id,
            aggregate_version=review.version,
            event_type="access_review.due.v1",
            payload={
                "review_id": str(review.id),
                "review_type": review.review_type,
                "population_count": review.items.count(),
                "due_at": review.due_at.isoformat(),
            },
            idempotency_key=f"access-review-due:{review.id}:{review.version}",
            tenant_id=membership.tenant_id,
            actor_id=membership.identity_id,
        )
        reviews.append(review)
    return reviews


def _revoke_item(item: AccessReviewItem, membership) -> str:
    source_id = item.source_object_id
    if item.assignment_type in {
        AccessReview.ReviewType.MEMBERSHIP,
        AccessReview.ReviewType.PRIVILEGED_ROLE,
        AccessReview.ReviewType.AUDIT_ACCESS,
    }:
        target = TenantMembership.objects.get(pk=source_id, tenant_id=membership.tenant_id)
        target.status = TenantMembership.Status.REVOKED
        target.version += 1
        target.save(update_fields=("status", "version"))
    elif item.assignment_type == AccessReview.ReviewType.PURPOSE_GRANT:
        grant = AccessGrant.objects.get(pk=source_id, tenant_id=membership.tenant_id)
        grant.status = AccessGrant.Status.REVOKED
        grant.version += 1
        grant.save(update_fields=("status", "version"))
    elif item.assignment_type == AccessReview.ReviewType.EMERGENCY_GRANT:
        request = EmergencyAccessRequest.objects.get(pk=source_id, tenant_id=membership.tenant_id)
        revoke_emergency_access(request=request, actor=membership.identity)
    else:
        raise ValidationError("Unsupported review assignment")
    item.revoked_at = timezone.now()
    item.remediation_state = AccessReview.RemediationState.COMPLETED
    item.save(update_fields=("revoked_at", "remediation_state"))
    record_governance_event(
        membership=membership,
        action="ACCESS_REVIEW_REVOCATION",
        target_type=item.assignment_type.lower(),
        target_id=source_id,
        review_id=str(item.review_id),
    )
    return source_id


@transaction.atomic
def complete_access_review(
    *, membership, review_id, if_match_version: int, decisions: list[dict]
) -> AccessReview:
    _authorize(membership)
    review = AccessReview.objects.select_for_update().get(
        pk=review_id, tenant_id=membership.tenant_id
    )
    if review.reviewer_id and review.reviewer_id != membership.identity_id:
        raise PermissionDenied("Access review unavailable")
    if review.version != if_match_version:
        raise ValidationError({"version": "Access review changed; reload before deciding."})
    if not decisions:
        raise ValidationError({"decisions": "At least one decision is required."})
    counts: Counter[str] = Counter()
    findings = []
    revocations = []
    seen: set[str] = set()
    for value in decisions:
        item_id = str(value.get("item_id", ""))
        if not item_id or item_id in seen:
            raise ValidationError({"decisions": "Decision items must be unique."})
        seen.add(item_id)
        item = review.items.select_for_update().get(pk=item_id)
        decision = str(value.get("decision", ""))
        if decision not in AccessReviewItem.Decision.values[1:]:
            raise ValidationError({"decision": "Unsupported review decision."})
        if item.subject_id == membership.identity_id:
            raise ValidationError({"reviewer": "Reviewers cannot decide their own access."})
        finding = str(value.get("finding", "")).strip()
        item.decision = decision
        item.finding = finding
        if finding:
            findings.append({"item_id": str(item.id), "finding": finding})
        if decision == AccessReviewItem.Decision.REVOKE:
            item.remediation_state = AccessReview.RemediationState.IN_PROGRESS
            item.save(update_fields=("decision", "finding", "remediation_state"))
            revocations.append(_revoke_item(item, membership))
        elif decision == AccessReviewItem.Decision.EXCEPTION:
            owner_id = value.get("exception_owner_id")
            expires_at = parse_datetime(str(value.get("exception_expires_at", "")))
            if not owner_id or expires_at is None or expires_at <= timezone.now():
                raise ValidationError(
                    {"exception": "Exceptions require an owner and future expiry."}
                )
            owner = TenantMembership.objects.filter(
                tenant_id=membership.tenant_id,
                identity_id=owner_id,
                status=TenantMembership.Status.ACTIVE,
            ).first()
            if owner is None:
                raise ValidationError({"exception_owner_id": "Owner is unavailable."})
            item.exception_owner = owner.identity
            item.exception_expires_at = expires_at
            item.remediation_state = AccessReview.RemediationState.PENDING
            item.save(
                update_fields=(
                    "decision",
                    "finding",
                    "exception_owner",
                    "exception_expires_at",
                    "remediation_state",
                )
            )
        else:
            item.remediation_state = AccessReview.RemediationState.NOT_REQUIRED
            item.save(update_fields=("decision", "finding", "remediation_state"))
        counts[decision] += 1
    review.state = AccessReview.State.COMPLETED
    review.completed_at = timezone.now()
    review.decision_counts = dict(counts)
    review.findings = findings
    review.revocations = revocations
    review.remediation_state = (
        AccessReview.RemediationState.PENDING
        if counts[AccessReviewItem.Decision.EXCEPTION]
        else AccessReview.RemediationState.COMPLETED
    )
    review.version += 1
    review.save()
    record_governance_event(
        membership=membership,
        action="ACCESS_REVIEW_COMPLETE",
        target_type="access_review",
        target_id=review.id,
        decision_counts=dict(counts),
        revocation_count=len(revocations),
    )
    return review


@transaction.atomic
def mark_overdue_reviews() -> int:
    reviews = list(
        AccessReview.objects.select_for_update().filter(
            state__in=[AccessReview.State.PENDING, AccessReview.State.IN_PROGRESS],
            due_at__lt=timezone.now(),
        )
    )
    for review in reviews:
        review.state = AccessReview.State.OVERDUE
        review.remediation_state = AccessReview.RemediationState.OVERDUE
        review.version += 1
        review.save(update_fields=("state", "remediation_state", "version", "updated_at"))
    return len(reviews)


@transaction.atomic
def expire_review_exceptions() -> int:
    items = list(
        AccessReviewItem.objects.select_for_update()
        .select_related("review", "review__created_by")
        .filter(
            decision=AccessReviewItem.Decision.EXCEPTION,
            exception_expires_at__lte=timezone.now(),
            revoked_at__isnull=True,
        )
    )
    for item in items:
        membership = TenantMembership.objects.filter(
            tenant_id=item.review.tenant_id,
            identity=item.review.created_by,
            role=TenantMembership.Role.TENANT_ADMIN,
        ).first()
        if membership is None:
            item.remediation_state = AccessReview.RemediationState.OVERDUE
            item.save(update_fields=("remediation_state",))
            continue
        _revoke_item(item, membership)
        item.remediation_state = AccessReview.RemediationState.OVERDUE
        item.save(update_fields=("remediation_state",))
    return len(items)
