from dataclasses import replace

import pytest
from django.conf import settings
from django.test import Client, override_settings

from modules.candidate.models import ResumeAsset
from modules.identity.local_auth import issue_local_candidate_bootstrap
from modules.identity.models import SessionCredential
from modules.recruiting.models import Opening

pytestmark = pytest.mark.django_db
LOCAL_CACHE = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "local-candidate-session-tests",
    }
}


@override_settings(CACHES=LOCAL_CACHE)
def test_one_time_bootstrap_creates_verified_candidate_session_and_role_context():
    issued = issue_local_candidate_bootstrap()
    client = Client()
    response = client.get("/api/v1/__local__/synthetic-candidate-session", {"token": issued.token})

    assert response.status_code == 302
    assert response["Location"] == f"/roles/{issued.opening_id}/"
    credential = SessionCredential.objects.get(pk=client.session["session_credential_id"])
    assert str(credential.identity_id) == issued.candidate_id
    assert credential.assurance == SessionCredential.Assurance.VERIFIED_EMAIL_OTP
    assert credential.provider == "LOCAL_SYNTHETIC"
    page = client.get(response["Location"])
    assert page.status_code == 200
    assert b'data-resume-id=""' not in page.content
    assert b'data-consent-id=""' not in page.content
    replay = Client().get("/api/v1/__local__/synthetic-candidate-session", {"token": issued.token})
    assert replay.status_code == 404


@override_settings(CACHES=LOCAL_CACHE)
def test_repeated_bootstrap_restores_the_synthetic_resume_fixture():
    first = issue_local_candidate_bootstrap()
    opening_count = Opening.objects.count()
    ResumeAsset.objects.filter(is_current=True).update(
        scan_status=ResumeAsset.ScanStatus.SCAN_FAILED,
        parse_status=ResumeAsset.ParseStatus.PARSE_FAILED,
    )

    issued = issue_local_candidate_bootstrap()
    client = Client()
    response = client.get("/api/v1/__local__/synthetic-candidate-session", {"token": issued.token})
    page = client.get(response["Location"])

    assert page.status_code == 200
    assert issued.opening_id == first.opening_id
    assert Opening.objects.count() == opening_count
    assert b'data-resume-id=""' not in page.content
    assert b'data-consent-id=""' not in page.content


@override_settings(
    CACHES=LOCAL_CACHE,
    LOCAL_SYNTHETIC_AUTH_ENABLED=True,
    ENV=replace(settings.ENV, app_env="production"),
)
def test_candidate_bootstrap_runtime_guard_fails_closed_in_production():
    response = Client().get("/api/v1/__local__/synthetic-candidate-session", {"token": "x" * 48})
    assert response.status_code == 404
