from __future__ import annotations

import uuid

import pytest

from modules.operations.concurrency import strong_etag
from modules.recruiting.models import CandidateFacingStatus
from modules.tenancy.models import TenantMembership
from tests.factories import (
    ApplicationFactory,
    CandidateCapabilityFactory,
    CandidateProfileFactory,
    MembershipFactory,
    NotificationFactory,
    OpeningFactory,
)

pytestmark = pytest.mark.django_db

PUBLIC_STATUSES = {
    "APPLIED",
    "PROFILE_VIEWED",
    "SHORTLISTED",
    "RECRUITER_INTERESTED",
    "INTERVIEW_REQUESTED",
    "OFFER_MADE",
    "NOT_SELECTED",
    "WITHDRAWN",
}


def _candidate(profile, api_client):
    CandidateCapabilityFactory(identity=profile.identity, assigned_by=profile.identity)
    api_client.force_login(profile.identity)


def _recruiter_for(opening, api_client):
    membership = MembershipFactory(tenant=opening.tenant, recruiter=True)
    api_client.force_login(membership.identity)
    return membership


def test_progress_exposes_only_eight_candidate_statuses_and_no_internal_state(api_client):
    profile = CandidateProfileFactory()
    _candidate(profile, api_client)
    app = ApplicationFactory(
        opening=OpeningFactory(open=True),
        candidate_profile_id=profile.id,
        submitted=True,
        candidate_status=CandidateFacingStatus.APPLIED,
    )
    app.history.create(
        tenant=app.tenant,
        prior_state="",
        new_state="SUBMITTED",
        published_candidate_status="APPLIED",
        actor=profile.identity,
        idempotency_key=f"history-{uuid.uuid4()}",
    )

    response = api_client.get("/api/v1/candidate/applications")

    assert response.status_code == 200
    assert {item["candidate_status"] for item in response.data} <= PUBLIC_STATUSES
    encoded = str(response.data)
    assert "internal_status" not in encoded
    assert "prior_state" not in encoded
    assert "new_state" not in encoded


@pytest.mark.parametrize(
    ("internal", "suggestion"),
    [
        ("SHORTLISTED", "SHORTLISTED"),
        ("CONTACTED", "RECRUITER_INTERESTED"),
        ("SCREENING", "RECRUITER_INTERESTED"),
        ("INTERVIEWING", "INTERVIEW_REQUESTED"),
        ("OFFERED", "OFFER_MADE"),
        ("REJECTED", "NOT_SELECTED"),
        ("SOURCED", None),
        ("NOT_RELEVANT", None),
        ("HIRED", None),
    ],
)
def test_status_preview_maps_internal_status_to_nullable_suggestion(
    api_client, internal, suggestion
):
    opening = OpeningFactory(open=True)
    app = ApplicationFactory(opening=opening, submitted=True)
    membership = _recruiter_for(opening, api_client)

    response = api_client.post(
        f"/api/v1/tenants/{opening.tenant_id}/applications/{app.id}/status-preview",
        {"internal_status": internal},
        format="json",
        HTTP_X_TENANT_ID=str(opening.tenant_id),
        HTTP_IF_MATCH=strong_etag(app.id, app.version),
    )

    assert response.status_code == 200
    assert response.data["suggested_candidate_status"] == suggestion
    assert response.data["published"] is False
    assert membership.role == TenantMembership.Role.RECRUITER


def test_explicit_recruiter_publication_updates_only_target_application(api_client):
    profile = CandidateProfileFactory()
    first_opening = OpeningFactory(open=True)
    second_opening = OpeningFactory(tenant=first_opening.tenant, open=True)
    first = ApplicationFactory(
        opening=first_opening, candidate_profile_id=profile.id, submitted=True
    )
    second = ApplicationFactory(
        opening=second_opening, candidate_profile_id=profile.id, submitted=True
    )
    _recruiter_for(first_opening, api_client)
    preview = api_client.post(
        f"/api/v1/tenants/{first.tenant_id}/applications/{first.id}/status-preview",
        {"internal_status": "INTERVIEWING"},
        format="json",
        HTTP_X_TENANT_ID=str(first.tenant_id),
        HTTP_IF_MATCH=strong_etag(first.id, first.version),
    )

    response = api_client.post(
        f"/api/v1/tenants/{first.tenant_id}/applications/{first.id}/status-publish",
        {
            "preview_id": preview.data["preview_id"],
            "candidate_status": "INTERVIEW_REQUESTED",
            "confirm": True,
            "notify_channels": [],
        },
        format="json",
        HTTP_X_TENANT_ID=str(first.tenant_id),
        HTTP_IF_MATCH=preview["ETag"],
        HTTP_IDEMPOTENCY_KEY=f"publish-{uuid.uuid4()}",
    )

    assert response.status_code == 202
    first.refresh_from_db()
    second.refresh_from_db()
    assert first.candidate_status == "INTERVIEW_REQUESTED"
    assert second.candidate_status == "APPLIED"


def test_unmapped_preview_cannot_publish_null_or_unapproved_value(api_client):
    opening = OpeningFactory(open=True)
    app = ApplicationFactory(opening=opening, submitted=True)
    _recruiter_for(opening, api_client)
    preview = api_client.post(
        f"/api/v1/tenants/{app.tenant_id}/applications/{app.id}/status-preview",
        {"internal_status": "HIRED"},
        format="json",
        HTTP_X_TENANT_ID=str(app.tenant_id),
        HTTP_IF_MATCH=strong_etag(app.id, app.version),
    )
    response = api_client.post(
        f"/api/v1/tenants/{app.tenant_id}/applications/{app.id}/status-publish",
        {"preview_id": preview.data["preview_id"], "candidate_status": None, "confirm": True},
        format="json",
        HTTP_X_TENANT_ID=str(app.tenant_id),
        HTTP_IF_MATCH=preview["ETag"],
        HTTP_IDEMPOTENCY_KEY=f"publish-{uuid.uuid4()}",
    )
    invalid = api_client.post(
        f"/api/v1/tenants/{app.tenant_id}/applications/{app.id}/status-publish",
        {
            "preview_id": preview.data["preview_id"],
            "candidate_status": "HIRED",
            "confirm": True,
        },
        format="json",
        HTTP_X_TENANT_ID=str(app.tenant_id),
        HTTP_IF_MATCH=preview["ETag"],
        HTTP_IDEMPOTENCY_KEY=f"publish-{uuid.uuid4()}",
    )
    assert response.status_code == invalid.status_code == 422


def test_candidate_notification_projection_never_exposes_sending(api_client):
    profile = CandidateProfileFactory()
    _candidate(profile, api_client)
    app = ApplicationFactory(
        opening=OpeningFactory(open=True), candidate_profile_id=profile.id, submitted=True
    )
    NotificationFactory(
        application_id=app.id,
        candidate_profile_id=profile.id,
        tenant_id=app.tenant_id,
        sending=True,
    )

    response = api_client.get(f"/api/v1/candidate/applications/{app.id}")

    assert response.status_code == 200
    assert response.data["notification_states"][0]["state"] == "PENDING"
    assert "SENDING" not in str(response.data)
