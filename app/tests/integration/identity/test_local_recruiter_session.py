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


@override_settings(CACHES=LOCAL_CACHE, FRONTEND_REACT_ROUTES={})
def test_local_fixture_matches_full_engineer_query_without_promoting_admin_records():
    from modules.ai.intent_schema import deterministic_fallback
    from modules.candidate.models import CandidateProfile
    from modules.identity.local_auth import BASE_OPENING_ID, _rls_context
    from modules.recruiting.models import RecruiterEnteredCandidate
    from modules.recruiting.recruiter_entered import create_recruiter_entered_candidate
    from modules.tenancy.models import TenantMembership

    issued = issue_local_recruiter_bootstrap()
    client = Client()
    assert (
        client.get(
            "/api/v1/__local__/synthetic-recruiter-session", {"token": issued.token}
        ).status_code
        == 302
    )
    with _rls_context(tenant_id=issued.tenant_id):
        membership = TenantMembership.objects.get(
            tenant_id=issued.tenant_id, identity_id=issued.recruiter_id
        )
        before = CandidateProfile.objects.count()
        record = create_recruiter_entered_candidate(
            membership=membership,
            actor=membership.identity,
            values={
                "confirm_synthetic": True,
                "display_name": "Synthetic Organization Record",
                "location": {"display": "Bengaluru"},
                "experience_years": 5,
                "skills": ["Python"],
            },
        )
        assert record.source_type == RecruiterEnteredCandidate.SOURCE_TYPE
        assert CandidateProfile.objects.count() == before
    criteria = deterministic_fallback(
        "Python engineer in Bengaluru with at least 5 years experience", {"type": "AD_HOC"}
    ).criteria.model_dump(mode="json", exclude_none=True)
    headers = {"X-Tenant-ID": issued.tenant_id}
    base = f"/api/v1/tenants/{issued.tenant_id}"
    response = client.post(
        f"{base}/searches", criteria, content_type="application/json", headers=headers
    )
    assert response.status_code == 200
    items = response.json()["items"]
    assert issued.candidate_id in [item["candidate_id"] for item in items]
    assert str(record.pk) not in [item["candidate_id"] for item in items]
    detail = client.get(
        f"{base}/candidates/{issued.candidate_id}",
        {"search_id": response.json()["search_id"]},
        headers=headers,
    )
    assert detail.status_code == 200
    assert detail.json()["findings"][0]["code"] == "SHORT_TENURE"
    assert detail.json()["findings"][0]["informational_only"] is True
    # This fixture explicitly approves the recruiter audience, not MATCHING_ROLES.
    criteria["context"] = {"type": "OPENING", "opening_id": str(BASE_OPENING_ID)}
    scoped = client.post(
        f"{base}/searches", criteria, content_type="application/json", headers=headers
    )
    assert scoped.status_code == 200
    assert issued.candidate_id not in [item["candidate_id"] for item in scoped.json()["items"]]
