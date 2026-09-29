import uuid
from datetime import timedelta

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from modules.candidate.models import CandidateProfile, VisibilityRule
from modules.candidate.visibility import replace_visibility, withdraw_consent
from modules.operations.concurrency import strong_etag
from tests.factories import (
    CandidateProfileFactory,
    ConsentRecordFactory,
    IdentityFactory,
)

pytestmark = [pytest.mark.django_db, pytest.mark.security]


def apply(profile, consent, **values):
    return replace_visibility(
        identity=profile.identity,
        profile=profile,
        if_match=strong_etag(profile.id, profile.version),
        values={"consent_record_id": consent.id, **values},
    )


def test_approved_recruiters_requires_explicit_audience():
    consent = ConsentRecordFactory()
    with pytest.raises(ValidationError):
        apply(consent.profile, consent, mode="APPROVED_RECRUITERS", approved_tenant_ids=[])


def test_matching_roles_requires_deterministic_preferences():
    consent = ConsentRecordFactory()
    with pytest.raises(ValidationError):
        apply(consent.profile, consent, mode="MATCHING_ROLES", matching_preferences={})


def test_all_four_visibility_modes_and_immediate_hiding():
    for mode in VisibilityRule.Mode.values:
        profile = CandidateProfileFactory(profile_state=CandidateProfile.State.PUBLISHED)
        consent = ConsentRecordFactory(profile=profile)
        values = {"mode": mode}
        if mode == "APPROVED_RECRUITERS":
            values["approved_tenant_ids"] = [str(uuid.uuid4())]
        if mode == "MATCHING_ROLES":
            values["matching_preferences"] = {"roles": ["Engineer"]}
        rule = apply(profile, consent, **values)
        assert rule.mode == mode
        if mode == "NOT_LOOKING":
            profile.refresh_from_db()
            assert profile.profile_state == CandidateProfile.State.HIDDEN


def test_consent_must_be_current_and_owned():
    profile = CandidateProfileFactory()
    other = ConsentRecordFactory()
    with pytest.raises(PermissionDenied):
        apply(profile, other, mode="NOT_LOOKING")
    expired = ConsentRecordFactory(
        profile=profile, expires_at=timezone.now() - timedelta(seconds=1)
    )
    with pytest.raises(PermissionDenied):
        apply(profile, expired, mode="NOT_LOOKING")


def test_withdrawal_hides_profile_and_supersedes_visibility():
    profile = CandidateProfileFactory(profile_state=CandidateProfile.State.PUBLISHED)
    consent = ConsentRecordFactory(profile=profile)
    rule = apply(
        profile, consent, mode="MATCHING_ROLES", matching_preferences={"roles": ["Engineer"]}
    )
    withdraw_consent(identity=profile.identity, profile=profile)
    profile.refresh_from_db()
    consent.refresh_from_db()
    rule.refresh_from_db()
    assert profile.profile_state == CandidateProfile.State.HIDDEN
    assert consent.withdrawn_at and rule.superseded_at


def test_cross_candidate_cannot_change_visibility():
    profile = CandidateProfileFactory()
    consent = ConsentRecordFactory(profile=profile)
    with pytest.raises(CandidateProfile.DoesNotExist):
        replace_visibility(
            identity=IdentityFactory(),
            profile=profile,
            if_match=strong_etag(profile.id, profile.version),
            values={"mode": "NOT_LOOKING", "consent_record_id": consent.id},
        )
