from __future__ import annotations

import uuid

import pytest

from modules.operations.concurrency import strong_etag
from modules.recruiting.models import Application
from tests.factories import (
    ApplicationFactory,
    CandidateCapabilityFactory,
    CandidateProfileFactory,
    ConsentRecordFactory,
    OpeningFactory,
    ResumeAssetFactory,
)

pytestmark = pytest.mark.django_db


def _signed_in_candidate(api_client):
    profile = CandidateProfileFactory()
    CandidateCapabilityFactory(identity=profile.identity, assigned_by=profile.identity)
    api_client.force_login(profile.identity)
    return profile


def _payload(profile, opening):
    resume = ResumeAssetFactory(profile=profile, clean=True)
    consent = ConsentRecordFactory(
        profile=profile,
        purpose="APPLICATION_SUBMISSION",
        field_scope=["application", "resume", "notifications"],
        audience_scope={"opening_id": str(opening.id), "tenant_id": str(opening.tenant_id)},
    )
    return {
        "opening_id": str(opening.id),
        "resume_id": str(resume.id),
        "answers": {},
        "consent_record_id": str(consent.id),
        "notification_preferences": {"email": True, "whatsapp": False},
    }


def test_closed_opening_rejects_submission_without_partial_application(api_client):
    profile = _signed_in_candidate(api_client)
    opening = OpeningFactory(closed=True)
    response = api_client.post(
        "/api/v1/candidate/applications",
        _payload(profile, opening),
        format="json",
        HTTP_IDEMPOTENCY_KEY=f"submit-{uuid.uuid4()}",
    )
    assert response.status_code == 422
    assert not Application.objects.filter(candidate_profile_id=profile.id).exists()


def test_stale_withdrawal_returns_reconciliation_and_does_not_change_state(api_client):
    profile = _signed_in_candidate(api_client)
    app = ApplicationFactory(
        opening=OpeningFactory(open=True),
        candidate_profile_id=profile.id,
        submitted=True,
        version=2,
    )
    response = api_client.post(
        f"/api/v1/candidate/applications/{app.id}/withdraw",
        {"candidate_status": "WITHDRAWN", "confirm": True},
        format="json",
        HTTP_IF_MATCH='"stale"',
        HTTP_IDEMPOTENCY_KEY=f"withdraw-{uuid.uuid4()}",
    )
    assert response.status_code == 409
    assert set(response.data) >= {
        "current",
        "attempted",
        "changed_fields",
        "current_etag",
    }
    app.refresh_from_db()
    assert app.candidate_status == "APPLIED"


def test_notification_failure_does_not_roll_back_published_status(api_client, monkeypatch):
    from modules.communications import application_notifications

    profile = CandidateProfileFactory()
    opening = OpeningFactory(open=True)
    app = ApplicationFactory(
        opening=opening,
        candidate_profile_id=profile.id,
        submitted=True,
        notify_email=True,
    )
    recruiter = __import__("tests.factories", fromlist=["MembershipFactory"]).MembershipFactory(
        tenant=opening.tenant, recruiter=True
    )
    api_client.force_login(recruiter.identity)
    preview = api_client.post(
        f"/api/v1/tenants/{app.tenant_id}/applications/{app.id}/status-preview",
        {"internal_status": "SHORTLISTED"},
        format="json",
        HTTP_X_TENANT_ID=str(app.tenant_id),
        HTTP_IF_MATCH=strong_etag(app.id, app.version),
    )

    monkeypatch.setattr(
        application_notifications,
        "queue_application_status_notifications",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("synthetic provider outage")),
    )
    response = api_client.post(
        f"/api/v1/tenants/{app.tenant_id}/applications/{app.id}/status-publish",
        {
            "preview_id": preview.data["preview_id"],
            "candidate_status": "SHORTLISTED",
            "confirm": True,
            "notify_channels": ["EMAIL"],
        },
        format="json",
        HTTP_X_TENANT_ID=str(app.tenant_id),
        HTTP_IF_MATCH=preview["ETag"],
        HTTP_IDEMPOTENCY_KEY=f"publish-{uuid.uuid4()}",
    )

    assert response.status_code == 202
    app.refresh_from_db()
    assert app.candidate_status == "SHORTLISTED"
    assert response.data["notifications"][0]["state"] == "FAILED"


def test_cross_candidate_application_is_not_disclosed(api_client):
    owner = CandidateProfileFactory()
    other = _signed_in_candidate(api_client)
    app = ApplicationFactory(
        opening=OpeningFactory(open=True), candidate_profile_id=owner.id, submitted=True
    )
    assert owner.id != other.id

    response = api_client.get(f"/api/v1/candidate/applications/{app.id}")
    assert response.status_code == 404
