from dataclasses import replace
from datetime import timedelta

import pytest
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory
from django.test.utils import override_settings
from django.utils import timezone

from modules.identity.models import IdentityCapability, SessionCredential
from modules.identity.services import (
    assurance_from_claims,
    begin_step_up,
    complete_step_up,
    global_sign_out,
    link_identity_with_role,
    require_recent_step_up,
    revoke_session,
    sign_in,
)
from modules.operations.crypto import blind_index

pytestmark = pytest.mark.django_db


def _request_with_session(client):
    request = RequestFactory().post("/api/v1/security/step-up")
    request.session = client.session
    return request


def test_verified_email_is_unique_and_subject_mismatch_is_denied(identity):
    email = "candidate@synthetic.invalid"
    claims = {
        "sub": "different-cognito-subject",
        "email": email,
        "email_verified": True,
        "amr": ["otp"],
    }
    identity.email_lookup_hmac = blind_index(email, purpose="verified-email")
    identity.save(update_fields=("email_lookup_hmac",))
    with pytest.raises(PermissionDenied):
        link_identity_with_role(claims, workforce=False)


def test_candidate_and_workforce_assurance_are_enforced():
    assert (
        assurance_from_claims({"email_verified": True, "amr": ["otp"]}, workforce=False)
        == SessionCredential.Assurance.VERIFIED_EMAIL_OTP
    )
    with pytest.raises(PermissionDenied):
        assurance_from_claims({"email_verified": True, "amr": ["pwd"]}, workforce=True)
    assert (
        assurance_from_claims({"email_verified": True, "amr": ["mfa"]}, workforce=True)
        == SessionCredential.Assurance.WORKFORCE_MFA
    )


def test_session_revocation_and_subject_bound_recent_step_up(client, identity):
    IdentityCapability.objects.create(
        identity=identity,
        role=IdentityCapability.Role.CANDIDATE,
        assigned_by=identity,
    )
    request = _request_with_session(client)
    request.user = identity
    credential = sign_in(
        request,
        identity,
        claims={"email_verified": True, "amr": ["otp"]},
    )
    nonce, purpose = begin_step_up(request, purpose="CANDIDATE_DELETION")
    now = int(timezone.now().timestamp())
    evidence = complete_step_up(
        request,
        claims={
            "sub": identity.cognito_subject,
            "nonce": nonce,
            "auth_time": now,
            "email_verified": True,
            "amr": ["otp"],
        },
        expected_nonce=nonce,
        purpose=purpose,
    )
    assert require_recent_step_up(request, purpose=purpose) == evidence
    revoke_session(credential, reason="SECURITY_REVOKED")
    with pytest.raises(PermissionDenied):
        require_recent_step_up(request, purpose=purpose)


def test_step_up_rejects_stale_or_different_subject(client, identity):
    request = _request_with_session(client)
    request.user = identity
    sign_in(request, identity, claims={"email_verified": True, "amr": ["otp"]})
    nonce, purpose = begin_step_up(request, purpose="CANDIDATE_DELETION")
    with pytest.raises(PermissionDenied):
        complete_step_up(
            request,
            claims={
                "sub": "another-subject",
                "nonce": nonce,
                "auth_time": int((timezone.now() - timedelta(minutes=10)).timestamp()),
                "email_verified": True,
                "amr": ["otp"],
            },
            expected_nonce=nonce,
            purpose=purpose,
        )


def test_complete_sign_out_revokes_provider_token_and_local_session(client, identity, monkeypatch):
    request = _request_with_session(client)
    request.user = identity
    synthetic_refresh = "-".join(("synthetic", "refresh", "value"))
    credential = sign_in(
        request,
        identity,
        claims={"email_verified": True, "amr": ["otp"]},
        refresh_token=synthetic_refresh,
    )
    calls = []

    class Response:
        def raise_for_status(self):
            return None

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return Response()

    monkeypatch.setattr("modules.identity.services.httpx.post", fake_post)
    production_env = replace(settings.ENV, app_env="production")
    with override_settings(ENV=production_env):
        global_sign_out(request)
    credential.refresh_from_db()
    assert credential.revoked_at is not None
    assert credential.revocation_reason == "USER_SIGN_OUT"
    assert calls[0][0].endswith("/oauth2/revoke")
    assert calls[0][1]["data"]["token"] == synthetic_refresh
