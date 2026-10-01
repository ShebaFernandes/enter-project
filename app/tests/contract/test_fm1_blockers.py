import uuid
from datetime import timedelta

import pytest
from django.utils import timezone

from modules.recruiting.candidate_work import create_or_reuse_candidate_work
from modules.search.models import SearchDefinition
from modules.search.saved_searches import create_saved_search, get_saved_search
from modules.tenancy.models import Tenant
from tests.integration.recruiting.test_candidate_work_record import sourced_context


@pytest.mark.django_db
def test_management_route_bootstraps_only_authorized_tenant(api_client, recruiter):
    path = f"/tenants/{recruiter.tenant_id}/recruiter/candidates/{uuid.uuid4()}/"
    assert api_client.get(path).status_code == 403
    api_client.force_login(recruiter.identity)
    response = api_client.get(path)
    assert response.status_code == 200
    assert str(recruiter.tenant_id).encode() in response.content
    assert response["Cache-Control"] == "no-store, private"
    assert (
        api_client.get(path.replace(str(recruiter.tenant_id), str(uuid.uuid4()))).status_code == 403
    )
    assert api_client.get(path, HTTP_X_TENANT_ID=str(uuid.uuid4())).status_code in (403, 404)
    other = Tenant.objects.create(name="Other tenant", slug="other", status="ACTIVE")
    assert api_client.get(path.replace(str(recruiter.tenant_id), str(other.id))).status_code == 403
    recruiter.role = "TENANT_ADMIN"
    recruiter.save()
    assert api_client.get(path).status_code == 403
    recruiter.role = "RECRUITER"
    recruiter.status = "REVOKED"
    recruiter.save()
    assert api_client.get(path).status_code == 403


@pytest.mark.django_db
def test_recent_cleanup_preserves_work_and_saved_provenance(
    api_client, recruiter, profile_factory, search_payload
):
    search = sourced_context(profile=profile_factory(published=True), recruiter=recruiter)
    work, _ = create_or_reuse_candidate_work(
        membership=recruiter,
        candidate_id=search.results.get().candidate_profile_id,
        originating_search_id=search.id,
        trigger="VIEW",
    )
    saved_search = SearchDefinition.objects.create(
        tenant_id=recruiter.tenant_id,
        actor=recruiter.identity,
        context_type="AD_HOC",
        criteria_context={"type": "AD_HOC"},
        expires_at=timezone.now() - timedelta(days=1),
    )
    saved = create_saved_search(membership=recruiter, name="Preserved", search_id=saved_search.id)
    disposable = SearchDefinition.objects.create(
        tenant_id=recruiter.tenant_id,
        actor=recruiter.identity,
        context_type="AD_HOC",
        criteria_context={"type": "AD_HOC"},
    )
    api_client.force_login(recruiter.identity)
    for _ in range(8):
        response = api_client.post(
            f"/api/v1/tenants/{recruiter.tenant_id}/searches",
            search_payload,
            format="json",
            HTTP_X_TENANT_ID=str(recruiter.tenant_id),
        )
        assert response.status_code == 200
    work.refresh_from_db()
    search.refresh_from_db()
    assert work.originating_search_id == search.id
    assert search.expires_at <= timezone.now()
    assert not SearchDefinition.objects.filter(pk=disposable.id).exists()
    assert (
        SearchDefinition.objects.filter(
            tenant_id=recruiter.tenant_id,
            actor=recruiter.identity,
            saved__isnull=True,
            expires_at__gt=timezone.now(),
        ).count()
        == 6
    )
    assert get_saved_search(membership=recruiter, search_id=saved_search.id).id == saved.id
    url = f"/api/v1/tenants/{recruiter.tenant_id}/saved-searches/{saved_search.id}"
    assert api_client.get(url, HTTP_X_TENANT_ID=str(recruiter.tenant_id)).status_code == 200
    assert api_client.get(url, HTTP_X_TENANT_ID=str(uuid.uuid4())).status_code in (403, 404)
    other = Tenant.objects.create(name="Other tenant", slug="other", status="ACTIVE")
    assert api_client.get(
        url.replace(str(recruiter.tenant_id), str(other.id)),
        HTTP_X_TENANT_ID=str(other.id),
    ).status_code in (403, 404)
