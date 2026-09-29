from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from modules.candidate.models import CandidateProfile, CandidateSkill
from modules.candidate.services import publish_profile
from modules.operations.concurrency import strong_etag
from modules.operations.models import OutboxEvent
from tests.factories import (
    CandidateProfileFactory,
    ConsentRecordFactory,
    ResumeAssetFactory,
    VisibilityRuleFactory,
)

pytestmark = pytest.mark.django_db


def test_publish_requires_resume_skills_visibility_and_consent():
    profile = CandidateProfileFactory()
    with pytest.raises(ValidationError):
        publish_profile(
            identity=profile.identity, if_match=strong_etag(profile.id, profile.version)
        )


def test_complete_profile_publishes_and_sets_12_month_consent_expiry():
    profile = CandidateProfileFactory()
    CandidateSkill.objects.create(profile=profile, normalized_name="python", display_name="Python")
    ResumeAssetFactory(profile=profile, clean=True)
    consent = ConsentRecordFactory(profile=profile)
    VisibilityRuleFactory(
        profile=profile,
        consent_record=consent,
        actor=profile.identity,
        mode="MATCHING_ROLES",
        matching_preferences={"roles": ["Engineer"]},
    )
    published = publish_profile(
        identity=profile.identity, if_match=strong_etag(profile.id, profile.version)
    )
    assert published.profile_state == CandidateProfile.State.PUBLISHED
    assert (
        timedelta(days=364) < published.consent_expires_at - timezone.now() <= timedelta(days=365)
    )
    assert OutboxEvent.objects.filter(event_type="profile.published.v1").exists()
