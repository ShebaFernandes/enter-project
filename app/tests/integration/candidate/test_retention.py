from datetime import timedelta

import pytest
from django.utils import timezone

from modules.candidate.models import CandidateProfile
from modules.operations.models import OutboxEvent
from modules.privacy.deletion_service import create_active_process_exception
from modules.privacy.retention import (
    hide_expired_profiles,
    schedule_consent_renewals,
    schedule_exception_reviews,
)
from tests.factories import (
    ApplicationFactory,
    CandidateProfileFactory,
    IdentityFactory,
)

pytestmark = pytest.mark.django_db


def test_renewal_event_is_scheduled_30_days_before_12_month_expiry():
    CandidateProfileFactory(
        profile_state=CandidateProfile.State.PUBLISHED,
        consent_expires_at=timezone.now() + timedelta(days=29),
    )
    assert schedule_consent_renewals() == 1
    assert OutboxEvent.objects.filter(event_type="consent.renewal_due.v1").exists()


def test_expired_profile_is_deleted_without_renewal():
    profile = CandidateProfileFactory(
        profile_state=CandidateProfile.State.PUBLISHED,
        consent_expires_at=timezone.now() - timedelta(seconds=1),
    )
    assert hide_expired_profiles() == 1
    profile.refresh_from_db()
    assert profile.profile_state == CandidateProfile.State.DELETED


def test_due_active_process_exception_enters_review_with_minimized_event():
    profile = CandidateProfileFactory()
    exception = create_active_process_exception(
        profile=profile,
        application=ApplicationFactory(candidate_profile_id=profile.id, active=True),
        policy_version="retention-v1",
        legal_basis="Active hiring process",
        retained_data_scope=["application.answers"],
        review_date=timezone.now() + timedelta(days=1),
        terminating_event="APPLICATION_CLOSED",
        approved_by=IdentityFactory(),
        audit_references=[str(profile.id)],
    )
    exception.review_date = timezone.now() - timedelta(seconds=1)
    exception.save(update_fields=("review_date",))
    assert schedule_exception_reviews() == 1
    exception.refresh_from_db()
    assert exception.lifecycle_state == "UNDER_REVIEW" and exception.version == 2
    event = OutboxEvent.objects.get(
        event_type="rights.active_process_exception_changed.v1",
        aggregate_id=exception.id,
    )
    assert set(event.payload) == {"exception_id", "version"}
