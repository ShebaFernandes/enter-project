from datetime import timedelta

import pytest
from django.utils import timezone

from tests.contract.test_comparison_api import comparison_profile, comparison_search
from tests.security.test_search_handoffs import assured

pytestmark = [pytest.mark.django_db, pytest.mark.postgres]


@pytest.fixture
def selection(api_client, recruiter, profile_factory, settings):
    settings.SEARCH_WORKFLOW_HANDOFF_ENABLED = True
    assured(api_client, recruiter.identity)
    api_client.credentials(HTTP_X_TENANT_ID=str(recruiter.tenant_id))
    profiles = [
        comparison_profile(profile_factory=profile_factory, recruiter=recruiter, name_suffix=str(i))
        for i in range(2)
    ]
    search = comparison_search(recruiter=recruiter, profiles=profiles)
    search.expires_at = timezone.now() + timedelta(hours=1)
    search.save()
    url = f"/api/v1/tenants/{recruiter.tenant_id}/search-handoffs/comparison-selection"
    ids = [str(p.pk) for p in reversed(profiles)]
    response = api_client.post(
        url,
        {"search_id": str(search.pk), "candidate_ids": ids},
        format="json",
        HTTP_IDEMPOTENCY_KEY="comparison-test-retry-001",
    )
    assert response.status_code == 201, response.content
    return api_client, url, response.json()["token"], ids, profiles


def test_order_restore_and_conflict(selection):
    client, url, token, ids, _ = selection
    headers = {"HTTP_X_WORKFLOW_HANDOFF": token}
    response = client.get(url, **headers)
    assert response.status_code == 200
    assert response.json()["candidate_ids"] == ids
    assert "no-store" in response["Cache-Control"]
    etag = response.json()["etag"]
    changed = client.patch(
        url, {"candidate_ids": ids[:1]}, format="json", HTTP_IF_MATCH=etag, **headers
    )
    assert changed.status_code == 200, changed.content
    assert changed.json()["candidate_ids"] == ids[:1]
    stale = client.patch(url, {"candidate_ids": ids}, format="json", HTTP_IF_MATCH=etag, **headers)
    assert stale.status_code == 409


def test_hidden_candidate_denied_and_type_isolation(selection):
    client, url, token, _, profiles = selection
    headers = {"HTTP_X_WORKFLOW_HANDOFF": token}
    assert (
        client.get(url.replace("comparison-selection", "search-results"), **headers).status_code
        == 404
    )
    profiles[0].profile_state = "HIDDEN"
    profiles[0].save()
    assert client.get(url, **headers).status_code == 404


def test_outside_result_and_limit_rejected(selection):
    import uuid

    client, url, token, ids, _ = selection
    headers = {"HTTP_X_WORKFLOW_HANDOFF": token}
    etag = client.get(url, **headers).json()["etag"]
    for values in [[str(uuid.uuid4())], ids * 6]:
        response = client.patch(
            url, {"candidate_ids": values}, format="json", HTTP_IF_MATCH=etag, **headers
        )
        assert response.status_code in {404, 422}


@pytest.mark.parametrize("state", ["expired", "revoked", "session", "actor", "tenant"])
def test_bound_access_concealed(selection, state):
    from modules.identity.models import Identity
    from modules.search.models import SearchWorkflowHandoff
    from modules.tenancy.models import Tenant, TenantMembership

    client, url, token, _, _ = selection
    item = SearchWorkflowHandoff.objects.get(kind="comparison-selection")
    if state == "expired":
        item.expires_at = timezone.now() - timedelta(seconds=1)
        item.save()
    elif state == "revoked":
        item.state = "REVOKED"
        item.save()
    elif state == "session":
        assured(client, item.actor)
    elif state == "actor":
        actor = Identity.objects.create_user(cognito_subject="other-selection-actor")
        TenantMembership.objects.create(
            tenant=item.tenant, identity=actor, role="RECRUITER", status="ACTIVE"
        )
        assured(client, actor)
    else:
        tenant = Tenant.objects.create(name="Other", slug="other-selection", status="ACTIVE")
        TenantMembership.objects.create(
            tenant=tenant, identity=item.actor, role="RECRUITER", status="ACTIVE"
        )
        client.credentials(HTTP_X_TENANT_ID=str(tenant.pk))
        url = url.replace(str(item.tenant_id), str(tenant.pk))
    assert client.get(url, HTTP_X_WORKFLOW_HANDOFF=token).status_code == 404


def test_safe_return_and_no_arbitrary_url(selection):
    from modules.operations.crypto import decrypt
    from modules.search.models import SearchWorkflowHandoff

    client, url, token, ids, _ = selection
    headers = {
        "HTTP_X_WORKFLOW_HANDOFF": token,
        "HTTP_IDEMPOTENCY_KEY": "return-selection-retry-001",
    }
    rejected = client.post(
        url + "/return", {"return_url": "https://example.test"}, format="json", **headers
    )
    assert rejected.status_code == 422
    returned = client.post(url + "/return", {}, format="json", **headers)
    assert returned.status_code == 200
    path = returned.json()["return_path"]
    assert path.startswith("/tenants/") and "/recruiter/search/?view=results#handoff=" in path
    result_token = path.split("#handoff=")[1].split("&")[0]
    assert result_token != token
    response = client.get(
        url.replace("comparison-selection", "search-results"), HTTP_X_WORKFLOW_HANDOFF=result_token
    )
    assert response.status_code == 200
    item = SearchWorkflowHandoff.objects.get(kind="comparison-selection")
    assert ids[0].encode() not in bytes(item.payload_ciphertext)
    assert "return_url" not in decrypt(bytes(item.payload_ciphertext))
    assert token not in decrypt(bytes(item.payload_ciphertext))


def test_selection_has_no_recruiting_side_effects(selection):
    from modules.recruiting.models import Application, ShortlistEntry
    from modules.recruiting.work_models import CandidateWorkRecord as CandidateWork

    client, url, token, ids, _ = selection
    before = [m.objects.count() for m in (Application, CandidateWork, ShortlistEntry)]
    headers = {"HTTP_X_WORKFLOW_HANDOFF": token}
    state = client.get(url, **headers).json()
    assert (
        client.patch(
            url, {"candidate_ids": ids[::-1]}, format="json", HTTP_IF_MATCH=state["etag"], **headers
        ).status_code
        == 200
    )
    assert before == [m.objects.count() for m in (Application, CandidateWork, ShortlistEntry)]


def test_selection_rls_nonowner(selection, tenant):
    from tests.security.test_search_handoffs import test_handoff_forced_rls_with_nonowner_role

    test_handoff_forced_rls_with_nonowner_role(selection, tenant)


def test_selection_csrf_rate_limit_and_revoked_session(selection):
    from rest_framework.test import APIClient

    from modules.search.models import SearchWorkflowHandoff

    client, url, token, ids, _ = selection
    strict = APIClient(enforce_csrf_checks=True)
    strict.cookies = client.cookies
    item = SearchWorkflowHandoff.objects.get(kind="comparison-selection")
    response = strict.patch(
        url,
        {"candidate_ids": ids},
        format="json",
        HTTP_X_TENANT_ID=str(item.tenant_id),
        HTTP_X_WORKFLOW_HANDOFF=token,
    )
    assert response.status_code == 403
    for _ in range(61):
        response = client.get(url, HTTP_X_WORKFLOW_HANDOFF=token)
    assert response.status_code == 429
    item.credential.revoked_at = timezone.now()
    item.credential.save()
    assert client.get(url, HTTP_X_WORKFLOW_HANDOFF=token).status_code in {401, 403, 404}
