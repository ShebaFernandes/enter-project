import uuid
from datetime import timedelta

import pytest
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from modules.candidate.models import CandidateProfile
from modules.identity.models import SessionCredential, StepUpEvidence
from modules.operations.concurrency import strong_etag
from tests.factories import CandidateCapabilityFactory, make_candidate_profile, make_identity

pytestmark = [pytest.mark.django_db, pytest.mark.contract]


@pytest.fixture
def candidate_api():
    identity = make_identity()
    CandidateCapabilityFactory(identity=identity, assigned_by=identity)
    profile = make_candidate_profile(identity=identity)
    client = APIClient()
    client.force_authenticate(identity)
    return client, identity, profile


def test_profile_access_correction_etag_and_stale_conflict(candidate_api):
    client, _identity, profile = candidate_api
    response = client.get("/api/v1/candidate/profile")
    assert response.status_code == 200
    etag = response["ETag"]
    updated = client.patch(
        "/api/v1/candidate/profile",
        {"full_name": "Corrected Synthetic Name"},
        format="json",
        HTTP_IF_MATCH=etag,
        HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
    )
    assert updated.status_code == 200
    stale = client.patch(
        "/api/v1/candidate/profile",
        {"full_name": "Stale Name"},
        format="json",
        HTTP_IF_MATCH=etag,
        HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
    )
    assert stale.status_code == 409
    assert {"current", "attempted", "changed_fields", "current_etag"} <= set(stale.json())


@override_settings(
    AWS_REGION="ap-south-1",
    S3_ENDPOINT_URL="http://localhost:4566",
    RESUME_QUARANTINE_BUCKET="enter-resume-quarantine",
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "candidate-resume-upload-test",
        }
    },
)
def test_resume_upload_returns_short_lived_signed_quarantine_grant(candidate_api):
    client, _identity, _profile = candidate_api
    response = client.post(
        "/api/v1/candidate/resumes/uploads",
        {
            "filename": "synthetic-resume.pdf",
            "content_type": "application/pdf",
            "size_bytes": 1024,
            "sha256": "a" * 64,
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["upload_url"].startswith("http://localhost:4566/")
    assert "X-Amz-Signature=" in payload["upload_url"]
    assert payload["required_headers"] == {
        "Content-Type": "application/pdf",
        "x-amz-meta-sha256": "a" * 64,
    }
    state = client.get(f"/api/v1/candidate/resumes/{payload['resume_id']}")
    assert state.status_code == 200
    assert "X-RateLimit-Remaining" not in state


def test_immediate_hide_and_rights_status(candidate_api):
    client, _identity, profile = candidate_api
    response = client.post(
        "/api/v1/candidate/rights-requests",
        {"request_type": "HIDE_PROFILE"},
        format="json",
        HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
    )
    assert response.status_code == 202 and response.json()["state"] == "COMPLETED"
    profile.refresh_from_db()
    assert profile.profile_state == CandidateProfile.State.HIDDEN
    assert client.get("/api/v1/candidate/rights-requests").status_code == 200


@pytest.mark.parametrize("request_type", ["ACCESS", "WITHDRAW_CONSENT", "HIDE_PROFILE"])
def test_immediate_rights_actions_complete_via_api(candidate_api, request_type):
    client, _identity, _profile = candidate_api
    response = client.post(
        "/api/v1/candidate/rights-requests",
        {"request_type": request_type},
        format="json",
        HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
    )
    assert response.status_code == 202
    assert response.json()["state"] == "COMPLETED"


def test_rights_correction_is_validated_and_applied_immediately(candidate_api):
    client, _identity, profile = candidate_api
    corrected = client.post(
        "/api/v1/candidate/rights-requests",
        {
            "request_type": "CORRECTION",
            "correction": {"full_name": "Corrected Synthetic Candidate"},
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
    )
    assert corrected.status_code == 202 and corrected.json()["state"] == "COMPLETED"
    assert client.get("/api/v1/candidate/profile").json()["full_name"] == (
        "Corrected Synthetic Candidate"
    )
    invalid = client.post(
        "/api/v1/candidate/rights-requests",
        {
            "request_type": "CORRECTION",
            "correction": {"experience_years": "-1"},
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
    )
    assert invalid.status_code == 422
    profile.refresh_from_db()


def test_non_candidate_and_other_candidate_cannot_access_profile(candidate_api):
    client, _identity, _profile = candidate_api
    outsider = make_identity()
    client.force_authenticate(outsider)
    assert client.get("/api/v1/candidate/profile").status_code == 404


def test_support_escalation_is_owned_and_reason_is_not_returned(candidate_api):
    client, _identity, _profile = candidate_api
    created = client.post(
        "/api/v1/candidate/rights-requests",
        {"request_type": "EXPORT"},
        format="json",
        HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
    )
    request_id = created.json()["id"]
    response = client.post(
        f"/api/v1/candidate/rights-requests/{request_id}/escalations",
        {"reason": "Synthetic export support request"},
        format="json",
        HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
    )
    assert response.status_code == 202 and response.content == b""


def test_visibility_contract_validates_preferences_and_hides_immediately(candidate_api):
    client, _identity, profile = candidate_api
    etag = client.get("/api/v1/candidate/profile")["ETag"]
    invalid = client.put(
        "/api/v1/candidate/visibility",
        {
            "mode": "MATCHING_ROLES",
            "consent_record_id": str(uuid.uuid4()),
            "matching_preferences": {},
        },
        format="json",
        HTTP_IF_MATCH=etag,
        HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
    )
    assert invalid.status_code == 422
    response = client.put(
        "/api/v1/candidate/visibility",
        {"mode": "NOT_LOOKING", "consent_record_id": str(uuid.uuid4())},
        format="json",
        HTTP_IF_MATCH=etag,
        HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
    )
    assert response.status_code == 200 and response.json()["mode"] == "NOT_LOOKING"
    profile.refresh_from_db()
    assert profile.profile_state == CandidateProfile.State.HIDDEN
    assert response["ETag"] == strong_etag(profile.id, profile.version)


def test_delete_api_requires_subject_bound_recent_step_up(candidate_api):
    client, identity, profile = candidate_api
    denied = client.post(
        "/api/v1/candidate/rights-requests",
        {
            "request_type": "DELETE",
            "confirm_consequences": True,
            "step_up_proof": str(uuid.uuid4()),
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
    )
    assert denied.status_code == 404
    now = timezone.now()
    credential = SessionCredential.objects.create(
        identity=identity,
        session_key_hash=b"api-delete-session",
        provider="COGNITO",
        assurance=SessionCredential.Assurance.VERIFIED_EMAIL_OTP,
        authenticated_at=now,
        expires_at=now + timedelta(hours=1),
    )
    evidence = StepUpEvidence.objects.create(
        identity=identity,
        session_credential=credential,
        purpose="candidate-deletion",
        method=SessionCredential.Assurance.VERIFIED_EMAIL_OTP,
        nonce_hash=b"api-delete-proof",
        verified_at=now,
        expires_at=now + timedelta(minutes=10),
    )
    session = client.session
    session["session_credential_id"] = str(credential.id)
    session["step_up_evidence_id"] = str(evidence.id)
    session.save()
    accepted = client.post(
        "/api/v1/candidate/rights-requests",
        {"request_type": "DELETE", "confirm_consequences": True, "step_up_proof": str(evidence.id)},
        format="json",
        HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
    )
    assert accepted.status_code == 202
    profile.refresh_from_db()
    assert profile.profile_state == CandidateProfile.State.DELETION_PENDING


def test_delete_api_rejects_expired_step_up_and_missing_confirmation(candidate_api):
    client, identity, _profile = candidate_api
    now = timezone.now()
    credential = SessionCredential.objects.create(
        identity=identity,
        session_key_hash=b"expired-api-delete-session",
        provider="COGNITO",
        assurance=SessionCredential.Assurance.VERIFIED_EMAIL_OTP,
        authenticated_at=now - timedelta(hours=1),
        expires_at=now + timedelta(hours=1),
    )
    evidence = StepUpEvidence.objects.create(
        identity=identity,
        session_credential=credential,
        purpose="candidate-deletion",
        method=SessionCredential.Assurance.VERIFIED_EMAIL_OTP,
        nonce_hash=b"expired-api-delete-proof",
        verified_at=now - timedelta(minutes=20),
        expires_at=now - timedelta(seconds=1),
    )
    session = client.session
    session["session_credential_id"] = str(credential.id)
    session["step_up_evidence_id"] = str(evidence.id)
    session.save()
    expired = client.post(
        "/api/v1/candidate/rights-requests",
        {"request_type": "DELETE", "confirm_consequences": True, "step_up_proof": str(evidence.id)},
        format="json",
        HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
    )
    assert expired.status_code == 404
    unconfirmed = client.post(
        "/api/v1/candidate/rights-requests",
        {"request_type": "DELETE", "step_up_proof": str(evidence.id)},
        format="json",
        HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
    )
    assert unconfirmed.status_code == 422
