from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from modules.candidate.models import CandidateProfile, CandidateSkill
from modules.candidate.services import publish_profile
from modules.operations.concurrency import strong_etag
from modules.operations.models import OutboxEvent
from tests.factories import (
    ConsentRecordFactory,
    ResumeAssetFactory,
    VisibilityRuleFactory,
    make_candidate_profile,
)

pytestmark = pytest.mark.django_db


def test_publish_requires_resume_skills_visibility_and_consent():
    profile = make_candidate_profile()
    with pytest.raises(ValidationError):
        publish_profile(
            identity=profile.identity, if_match=strong_etag(profile.id, profile.version)
        )


def test_complete_profile_publishes_and_sets_12_month_consent_expiry():
    profile = make_candidate_profile()
    profile.current_role = "Engineer"
    profile.experience_years = 0
    profile.notice_period = "Immediate"
    profile.meaningful_work = "Built an accessible application."
    profile.role_categories = ["Engineer"]
    profile.preferred_locations = ["Bengaluru"]
    profile.work_arrangements = ["REMOTE"]
    profile.save()
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
    assert published.consent_expires_at is not None
    assert (
        timedelta(days=364) < published.consent_expires_at - timezone.now() <= timedelta(days=365)
    )
    assert OutboxEvent.objects.filter(event_type="profile.published.v1").exists()


def test_publication_requires_opportunity_and_meaningful_work_details():
    profile = make_candidate_profile()
    profile.current_role = ""
    profile.notice_period = ""
    profile.meaningful_work = " "
    profile.role_categories = []
    profile.preferred_locations = []
    profile.work_arrangements = []
    profile.save()
    with pytest.raises(ValidationError) as error:
        publish_profile(
            identity=profile.identity, if_match=strong_etag(profile.id, profile.version)
        )
    assert {
        "current_role",
        "notice_period",
        "meaningful_work",
        "role_categories",
        "preferred_locations",
        "work_arrangements",
    } <= set(error.value.message_dict)


def test_saving_reviewed_resume_makes_it_ready_without_reupload():
    from modules.candidate.services import update_profile

    profile = make_candidate_profile()
    resume = ResumeAssetFactory(profile=profile, clean=True)
    resume.parse_status = "REVIEW_REQUIRED"
    resume.save()
    update_profile(
        identity=profile.identity,
        if_match=strong_etag(profile.id, profile.version),
        values={"reviewed_resume_id": resume.id},
    )
    resume.refresh_from_db()
    assert resume.parse_status == "READY"


@pytest.mark.parametrize(
    "scan,parse",
    [("SCAN_FAILED", "REVIEW_REQUIRED"), ("CLEAN", "PARSING"), ("CLEAN", "PARSE_FAILED")],
)
def test_review_confirmation_cannot_bypass_processing(scan, parse):
    from modules.candidate.services import update_profile

    profile = make_candidate_profile()
    resume = ResumeAssetFactory(profile=profile, clean=True)
    resume.scan_status, resume.parse_status = scan, parse
    resume.save()
    with pytest.raises(ValidationError):
        update_profile(
            identity=profile.identity,
            if_match=strong_etag(profile.id, profile.version),
            values={"reviewed_resume_id": resume.id},
        )
    resume.refresh_from_db()
    assert resume.parse_status == parse


def test_cannot_confirm_another_candidates_resume():
    from modules.candidate.services import update_profile

    profile, other = make_candidate_profile(), make_candidate_profile()
    resume = ResumeAssetFactory(profile=other, clean=True)
    with pytest.raises(ValidationError):
        update_profile(
            identity=profile.identity,
            if_match=strong_etag(profile.id, profile.version),
            values={"reviewed_resume_id": resume.id},
        )
