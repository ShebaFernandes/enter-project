from dataclasses import replace

import pytest
from django.conf import settings
from django.test import Client, override_settings

from modules.identity.local_auth import issue_local_recruiter_bootstrap
from modules.identity.models import SessionCredential

pytestmark = pytest.mark.django_db

LOCAL_CACHE = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "local-recruiter-session-tests",
    }
}


@override_settings(CACHES=LOCAL_CACHE)
def test_one_time_bootstrap_creates_real_assured_recruiter_session_and_search():
    issued = issue_local_recruiter_bootstrap()
    client = Client()
    response = client.get("/api/v1/__local__/synthetic-recruiter-session", {"token": issued.token})
    assert response.status_code == 302
    assert response["Location"] == f"/tenants/{issued.tenant_id}/recruiter/search/"
    credential = SessionCredential.objects.get(pk=client.session["session_credential_id"])
    assert str(credential.identity_id) == issued.recruiter_id
    assert credential.assurance == SessionCredential.Assurance.WORKFORCE_MFA
    assert credential.provider == "LOCAL_SYNTHETIC"

    page = client.get(response["Location"])
    assert page.status_code == 200
    assert b"Signed in as recruiter" in page.content

    search = client.post(
        f"/api/v1/tenants/{issued.tenant_id}/searches",
        data={
            "context": {"type": "AD_HOC"},
            "groups": [
                {
                    "id": "3cdf5ee3-7861-4ca4-a8fe-bb97d1f2a357",
                    "purpose": "REQUIREMENT",
                    "operator": "ALL",
                    "label": "Skills",
                }
            ],
            "criteria": [
                {
                    "id": "f555fabb-4f95-48d4-94c0-a9ed4a682a0e",
                    "group_id": "3cdf5ee3-7861-4ca4-a8fe-bb97d1f2a357",
                    "field": "skill",
                    "operator": "CONTAINS",
                    "value": "Python",
                }
            ],
            "limit": 25,
        },
        content_type="application/json",
        headers={"X-Tenant-ID": issued.tenant_id},
    )
    assert search.status_code == 200
    result = next(
        item for item in search.json()["items"] if item["candidate_id"] == issued.candidate_id
    )
    assert result["candidate_id"] == issued.candidate_id
    assert result["findings"][0]["code"] == "SHORT_TENURE"
    assert result["findings"][0]["informational_only"] is True

    detail = client.get(
        f"/api/v1/tenants/{issued.tenant_id}/candidates/{issued.candidate_id}",
        {"search_id": search.json()["search_id"]},
        headers={"X-Tenant-ID": issued.tenant_id},
    )
    assert detail.status_code == 200
    assert detail.json()["findings"][0]["evidence"]["company"] == ("Synthetic Previous Employer")

    replay = Client().get("/api/v1/__local__/synthetic-recruiter-session", {"token": issued.token})
    assert replay.status_code == 404

    assert client.delete("/api/v1/session/sign-out").status_code == 204
    assert client.get(response["Location"]).status_code == 403


@override_settings(
    CACHES=LOCAL_CACHE,
    LOCAL_SYNTHETIC_AUTH_ENABLED=True,
    ENV=replace(settings.ENV, app_env="production"),
)
def test_local_bootstrap_runtime_guard_fails_closed_in_production():
    response = Client().get("/api/v1/__local__/synthetic-recruiter-session", {"token": "x" * 48})
    assert response.status_code == 404
