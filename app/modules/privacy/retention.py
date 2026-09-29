from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from modules.candidate.models import CandidateProfile
from modules.operations.outbox import enqueue

from .deletion_service import complete_due_deletion
from .models import ActiveProcessRetentionException, DataRightsRequest


def schedule_consent_renewals(*, now=None) -> int:
    now = now or timezone.now()
    due_after = now + timedelta(days=30)
    profiles = CandidateProfile.objects.filter(
        profile_state__in=[CandidateProfile.State.PUBLISHED, CandidateProfile.State.HIDDEN],
        consent_expires_at__lte=due_after,
        consent_expires_at__gt=now,
    )
    count = 0
    for profile in profiles:
        consent_expires_at = profile.consent_expires_at
        if consent_expires_at is None:
            continue
        consent_cycle = consent_expires_at.date().isoformat()
        enqueue(
            aggregate_type="candidate_profile",
            aggregate_id=profile.id,
            aggregate_version=profile.version,
            event_type="consent.renewal_due.v1",
            payload={
                "candidate_profile_id": str(profile.id),
                "consent_cycle": consent_cycle,
            },
            idempotency_key=f"consent-renewal:{profile.id}:{consent_cycle}",
            actor_id=profile.identity_id,
        )
        count += 1
    return count


def schedule_exception_reviews(*, now=None) -> int:
    now = now or timezone.now()
    due = ActiveProcessRetentionException.objects.filter(
        lifecycle_state=ActiveProcessRetentionException.State.ACTIVE,
        review_date__lte=now,
    )
    count = 0
    for exception in due:
        exception.lifecycle_state = ActiveProcessRetentionException.State.UNDER_REVIEW
        exception.version += 1
        exception.save(update_fields=("lifecycle_state", "version"))
        enqueue(
            aggregate_type="active_process_retention_exception",
            aggregate_id=exception.id,
            aggregate_version=exception.version,
            event_type="rights.active_process_exception_changed.v1",
            payload={"exception_id": str(exception.id), "version": exception.version},
            idempotency_key=f"retention-exception-review:{exception.id}:{exception.version}",
            actor_id=exception.approved_by_id,
        )
        count += 1
    return count


def expire_inactive_profiles(*, now=None) -> int:
    """Erase expired inactive profiles unless precisely scoped retention applies."""
    now = now or timezone.now()
    profiles = CandidateProfile.objects.filter(
        consent_expires_at__lte=now,
        profile_state=CandidateProfile.State.PUBLISHED,
    )
    count = 0
    for profile in profiles:
        has_exception = profile.retention_exceptions.filter(
            lifecycle_state__in=["ACTIVE", "UNDER_REVIEW"]
        ).exists()
        has_hold = (
            profile.legal_holds.filter(starts_at__lte=now)
            .filter(models.Q(ends_at__isnull=True) | models.Q(ends_at__gt=now))
            .exists()
        )
        request = DataRightsRequest.objects.create(
            profile=profile,
            request_type=DataRightsRequest.RequestType.DELETE,
            state=(
                DataRightsRequest.State.HELD
                if has_exception or has_hold
                else DataRightsRequest.State.IN_PROGRESS
            ),
            scope={"basis": "INACTIVITY_RETENTION_EXPIRY"},
            expected_completion_at=now,
            safe_detail=(
                "Deletion is held for a limited identified scope"
                if has_exception or has_hold
                else "Retention period expired; deletion in progress"
            ),
        )
        profile.profile_state = CandidateProfile.State.DELETION_PENDING
        profile.version += 1
        profile.save(update_fields=("profile_state", "version", "updated_at"))
        if not has_exception and not has_hold:
            complete_due_deletion(request.id, force_due=True)
        count += 1
    return count


def hide_expired_profiles(*, now=None) -> int:
    """Backward-compatible worker name; expiry now performs required erasure."""
    return expire_inactive_profiles(now=now)


from django.db import models  # noqa: E402
