import uuid

import pytest

from tests.integration.recruiting.test_candidate_work_record import sourced_context


@pytest.mark.django_db
def test_authenticated_recruiter_candidate_work_notes_shortlist_and_conflict_api(
    api_client, profile_factory, recruiter
):
    profile = profile_factory(published=True)
    search = sourced_context(profile=profile, recruiter=recruiter)
    api_client.force_login(recruiter.identity)
    headers = {
        "HTTP_X_TENANT_ID": str(recruiter.tenant_id),
        "HTTP_IDEMPOTENCY_KEY": f"candidate-work-{uuid.uuid4()}",
    }
    created = api_client.post(
        f"/api/v1/tenants/{recruiter.tenant_id}/candidate-work",
        {
            "candidate_id": str(profile.id),
            "originating_search_id": str(search.id),
            "opening_id": None,
            "trigger": "VIEW",
        },
        format="json",
        **headers,
    )
    assert created.status_code == 201
    work_id = created.data["id"]
    note = api_client.post(
        f"/api/v1/tenants/{recruiter.tenant_id}/candidate-work/{work_id}/notes",
        {"body": "Synthetic contextual note"},
        format="json",
        HTTP_X_TENANT_ID=str(recruiter.tenant_id),
        HTTP_IDEMPOTENCY_KEY=f"candidate-note-{uuid.uuid4()}",
    )
    assert note.status_code == 201
    assert note.data["context_type"] == "CANDIDATE_WORK"
    updated = api_client.patch(
        f"/api/v1/tenants/{recruiter.tenant_id}/candidate-work/{work_id}",
        {"internal_status": "SHORTLISTED", "shortlisted": True},
        format="json",
        HTTP_X_TENANT_ID=str(recruiter.tenant_id),
        HTTP_IDEMPOTENCY_KEY=f"candidate-update-{uuid.uuid4()}",
        HTTP_IF_MATCH=created["ETag"],
    )
    assert updated.status_code == 200
    assert updated.data["shortlisted"] is True
    assert updated.data["internal_status"] == "SHORTLISTED"
    stale = api_client.patch(
        f"/api/v1/tenants/{recruiter.tenant_id}/candidate-work/{work_id}",
        {"internal_status": "CONTACTED"},
        format="json",
        HTTP_X_TENANT_ID=str(recruiter.tenant_id),
        HTTP_IDEMPOTENCY_KEY=f"candidate-stale-{uuid.uuid4()}",
        HTTP_IF_MATCH=created["ETag"],
    )
    assert stale.status_code == 409
    assert stale.data["current"]["internal_status"] == "SHORTLISTED"
    assert stale.data["attempted"]["internal_status"] == "CONTACTED"


@pytest.mark.django_db
def test_tenant_admin_and_cross_tenant_requests_cannot_enumerate_candidate_work(
    api_client, profile_factory, recruiter
):
    from tests.factories import MembershipFactory, TenantFactory

    profile = profile_factory(published=True)
    search = sourced_context(profile=profile, recruiter=recruiter)
    other = MembershipFactory(tenant=TenantFactory(), tenant_admin=True)
    api_client.force_login(other.identity)
    response = api_client.post(
        f"/api/v1/tenants/{recruiter.tenant_id}/candidate-work",
        {
            "candidate_id": str(profile.id),
            "originating_search_id": str(search.id),
            "trigger": "VIEW",
        },
        format="json",
        HTTP_X_TENANT_ID=str(recruiter.tenant_id),
        HTTP_IDEMPOTENCY_KEY=f"candidate-denied-{uuid.uuid4()}",
    )
    assert response.status_code == 404
    assert "candidate" not in str(response.json()).casefold()
