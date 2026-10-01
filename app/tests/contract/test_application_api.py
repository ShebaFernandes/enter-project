from __future__ import annotations

import uuid
from typing import cast

import pytest
from django.utils import timezone

from modules.audit.models import AuditEvent
from modules.candidate.models import ConsentRecord
from modules.recruiting.models import Application, CandidateFacingStatus, Opening
from tests.factories import (
    CandidateCapabilityFactory,
    CandidateProfileFactory,
    ConsentRecordFactory,
    OpeningFactory,
    ResumeAssetFactory,
)

pytestmark = pytest.mark.django_db


def _candidate_client(api_client):
    profile = CandidateProfileFactory()
    CandidateCapabilityFactory(identity=profile.identity, assigned_by=profile.identity)
    api_client.force_login(profile.identity)
    return profile


def _submission(profile, opening, *, resume=None):
    resume = resume or ResumeAssetFactory(profile=profile, clean=True)
    consent = ConsentRecordFactory(
        profile=profile,
        purpose="APPLICATION_SUBMISSION",
        field_scope=["application", "resume", "notifications"],
        audience_scope={"opening_id": str(opening.id), "tenant_id": str(opening.tenant_id)},
    )
    return {
        "opening_id": str(opening.id),
        "resume_id": str(resume.id),
        "answers": {"motivation": "Synthetic application answer"},
        "consent_record_id": str(consent.id),
        "notification_preferences": {"email": True, "whatsapp": False},
    }


def test_public_opening_exposes_only_open_role_essentials(api_client):
    opening = cast(Opening, OpeningFactory(open=True))
    from modules.recruiting.models import OpeningPublicationLink
    from modules.tenancy.models import TenantMembership
    from tests.database.test_public_opening_projection import publish

    member = TenantMembership.objects.create(
        tenant=opening.tenant, identity=opening.created_by, role="RECRUITER", status="ACTIVE"
    )
    publish(opening, member)
    public_id = OpeningPublicationLink.objects.get(opening=opening).public_id

    response = api_client.get(f"/api/v1/public/openings/{public_id}")

    assert response.status_code == 200
    assert response.data["id"] == str(public_id)
    assert public_id != opening.id
    assert response.data["title"] == opening.title
    assert "tenant_id" not in response.data
    assert "business_unit_id" not in response.data
    assert "hiring_team_ids" not in response.data


def test_public_opening_hides_closed_role(api_client):
    opening = OpeningFactory(closed=True)
    response = api_client.get(f"/api/v1/public/openings/{opening.id}")
    assert response.status_code == 404


def test_one_verified_profile_can_submit_independent_applications(api_client):
    profile = _candidate_client(api_client)
    first = OpeningFactory(open=True)
    second = OpeningFactory(open=True)
    resume = ResumeAssetFactory(profile=profile, clean=True)

    first_response = api_client.post(
        "/api/v1/candidate/applications",
        _submission(profile, first, resume=resume),
        format="json",
        HTTP_IDEMPOTENCY_KEY=f"submit-{uuid.uuid4()}",
    )
    second_payload = _submission(profile, second, resume=resume)
    second_payload["answers"] = {"motivation": "A distinct answer"}
    second_response = api_client.post(
        "/api/v1/candidate/applications",
        second_payload,
        format="json",
        HTTP_IDEMPOTENCY_KEY=f"submit-{uuid.uuid4()}",
    )

    assert first_response.status_code == 201, first_response.data
    assert second_response.status_code == 201, second_response.data
    assert first_response.data["candidate_status"] == CandidateFacingStatus.APPLIED
    assert first_response.data["id"] != second_response.data["id"]
    applications = Application.objects.filter(candidate_profile_id=profile.id).order_by("id")
    assert applications.count() == 2
    assert {item.opening_id for item in applications} == {first.id, second.id}
    assert {item.answers["motivation"] for item in applications} == {
        "Synthetic application answer",
        "A distinct answer",
    }
    assert all(item.submitted_at is not None for item in applications)
    assert all(item.consent_context_id is not None for item in applications)
    audit = AuditEvent.objects.get(
        action="APPLICATION_SUBMITTED", target_id=first_response.data["id"]
    )
    assert "Synthetic application answer" not in str(audit.metadata)
    assert "@" not in str(audit.metadata)


def test_submission_is_idempotent_and_unique_per_opening(api_client):
    profile = _candidate_client(api_client)
    opening = OpeningFactory(open=True)
    payload = _submission(profile, opening)
    key = f"submit-{uuid.uuid4()}"

    first = api_client.post(
        "/api/v1/candidate/applications",
        payload,
        format="json",
        HTTP_IDEMPOTENCY_KEY=key,
    )
    replay = api_client.post(
        "/api/v1/candidate/applications",
        payload,
        format="json",
        HTTP_IDEMPOTENCY_KEY=key,
    )
    duplicate = api_client.post(
        "/api/v1/candidate/applications",
        payload,
        format="json",
        HTTP_IDEMPOTENCY_KEY=f"submit-{uuid.uuid4()}",
    )

    assert first.status_code == 201, first.data
    assert replay.status_code == 201, replay.data
    assert first.data == replay.data
    assert duplicate.status_code == 409
    assert (
        Application.objects.filter(opening_id=opening.id, candidate_profile_id=profile.id).count()
        == 1
    )


@pytest.mark.parametrize(
    ("mutation", "field"),
    [
        (lambda payload: payload.update({"answers": "invalid"}), "answers"),
        (
            lambda payload: payload.update(
                {"notification_preferences": {"email": "yes", "whatsapp": False}}
            ),
            "notification_preferences",
        ),
    ],
)
def test_submission_validation_is_atomic(api_client, mutation, field):
    profile = _candidate_client(api_client)
    opening = OpeningFactory(open=True)
    payload = _submission(profile, opening)
    mutation(payload)

    response = api_client.post(
        "/api/v1/candidate/applications",
        payload,
        format="json",
        HTTP_IDEMPOTENCY_KEY=f"submit-{uuid.uuid4()}",
    )

    assert response.status_code == 422
    assert field in response.data.get("errors", response.data)
    assert not Application.objects.filter(candidate_profile_id=profile.id).exists()


def test_withdrawal_is_candidate_confirmed_and_application_scoped(api_client):
    profile = _candidate_client(api_client)
    first = OpeningFactory(open=True)
    second = OpeningFactory(open=True)
    resume = ResumeAssetFactory(profile=profile, clean=True)
    application_ids = []
    for opening in (first, second):
        response = api_client.post(
            "/api/v1/candidate/applications",
            _submission(profile, opening, resume=resume),
            format="json",
            HTTP_IDEMPOTENCY_KEY=f"submit-{uuid.uuid4()}",
        )
        application_ids.append(response.data["id"])

    detail = api_client.get(f"/api/v1/candidate/applications/{application_ids[0]}")
    response = api_client.post(
        f"/api/v1/candidate/applications/{application_ids[0]}/withdraw",
        {"candidate_status": "WITHDRAWN", "confirm": True},
        format="json",
        HTTP_IF_MATCH=detail["ETag"],
        HTTP_IDEMPOTENCY_KEY=f"withdraw-{uuid.uuid4()}",
    )

    assert response.status_code == 200
    assert response.data["candidate_status"] == "WITHDRAWN"
    assert Application.objects.get(pk=application_ids[1]).candidate_status == "APPLIED"


def test_expired_or_withdrawn_consent_cannot_submit(api_client):
    profile = _candidate_client(api_client)
    opening = OpeningFactory(open=True)
    payload = _submission(profile, opening)
    ConsentRecord.objects.filter(pk=payload["consent_record_id"]).update(
        withdrawn_at=timezone.now()
    )

    response = api_client.post(
        "/api/v1/candidate/applications",
        payload,
        format="json",
        HTTP_IDEMPOTENCY_KEY=f"submit-{uuid.uuid4()}",
    )

    assert response.status_code == 422
    assert not Application.objects.filter(candidate_profile_id=profile.id).exists()


def test_application_rate_limit_returns_non_enumerating_problem(api_client, settings):
    profile = _candidate_client(api_client)
    opening = OpeningFactory(open=True)
    payload = _submission(profile, opening)
    from modules.abuse import service

    original = service.check
    service.check = lambda request, action, anomaly_score=0: (False, 0, 30)
    try:
        response = api_client.post(
            "/api/v1/candidate/applications",
            payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY=f"submit-{uuid.uuid4()}",
        )
    finally:
        service.check = original

    assert response.status_code == 429
    assert response["Retry-After"] == "30"
    assert "account" not in response.content.decode().casefold()
