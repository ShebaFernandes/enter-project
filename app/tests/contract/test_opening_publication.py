"""FM3 remediation: publication is an explicit, independently confirmed action."""

import uuid
from unittest.mock import patch

import pytest

from modules.recruiting.models import PublicOpeningProjection
from modules.recruiting.openings import update_opening

pytestmark = [pytest.mark.django_db, pytest.mark.postgres]


@pytest.fixture
def publication(api_client, opening_factory, tenant, tenant_admin):
    opening = opening_factory(tenant=tenant)
    api_client.force_login(tenant_admin.identity)
    api_client.credentials(HTTP_X_TENANT_ID=str(tenant.id))
    path = f"/api/v1/tenants/{tenant.id}/openings/{opening.id}/publication"
    return api_client, path, opening


def mutate(client, path, preview, action="publish", key=None, **overrides):
    body = {"confirmed": True}
    if action == "publish":
        body["preview_digest"] = preview["preview_digest"]
    body.update(overrides)
    return client.post(
        f"{path}/{action}",
        body,
        format="json",
        HTTP_IF_MATCH=preview["source_etag"],
        HTTP_IDEMPOTENCY_KEY=key or str(uuid.uuid4()),
    )


def test_independent_publication_lifecycle(publication):
    client, path, opening = publication
    response = client.get(path)
    assert response.status_code == 200
    preview = response.json()
    assert preview["internal_state"] == "OPEN"
    assert preview["publication_state"] == "UNPUBLISHED"
    assert client.get("/api/v1/public/openings").json()["items"] == []
    assert set(preview["public_fields"]) == {
        "id",
        "title",
        "description",
        "company_name",
        "about_company",
        "role_summary",
        "responsibilities",
        "requirements",
        "nice_to_have",
        "location",
        "work_mode",
        "employment_type",
        "published_at",
        "closes_at",
        "application_url",
    }
    key = str(uuid.uuid4())
    published = mutate(client, path, preview, key=key)
    assert published.status_code == 200
    assert published.json()["publication_state"] == "PUBLISHED"
    assert mutate(client, path, preview, key=key).json() == published.json()
    assert len(client.get("/api/v1/public/openings").json()["items"]) == 1
    assert published.json()["public_url"].encode() in client.get("/jobs/").content
    opening.refresh_from_db()
    assert opening.state == "OPEN"
    preview = client.get(path).json()
    key = str(uuid.uuid4())
    withdrawn = mutate(client, path, preview, "withdraw", key=key)
    assert withdrawn.status_code == 200
    assert withdrawn.json()["publication_state"] == "UNPUBLISHED"
    assert mutate(client, path, preview, "withdraw", key=key).json() == withdrawn.json()
    opening.refresh_from_db()
    assert opening.state == "OPEN"
    assert client.get("/api/v1/public/openings").json()["items"] == []
    assert published.json()["public_url"].encode() not in client.get("/jobs/").content


def test_confirmation_digest_and_etag_are_required(publication):
    client, path, opening = publication
    preview = client.get(path).json()
    assert mutate(client, path, preview, confirmed=False).status_code == 422
    assert mutate(client, path, preview, confirmed="true").status_code == 422
    assert mutate(client, path, preview, preview_digest="not-current").status_code == 409
    stale = {**preview, "source_etag": '"old"'}
    assert mutate(client, path, stale).status_code == 409
    opening.title = "A changed public title"
    opening.version += 1
    opening.save()
    fresh = client.get(path).json()
    assert mutate(client, path, fresh, preview_digest=preview["preview_digest"]).status_code == 409
    assert not PublicOpeningProjection.objects.exists()


def test_updates_require_new_preview_and_reopening_does_not_publish(publication, tenant_admin):
    client, path, opening = publication
    preview = client.get(path).json()
    assert mutate(client, path, preview).status_code == 200
    opening.refresh_from_db()
    opening = update_opening(opening=opening, membership=tenant_admin, changes={"title": "Updated"})
    assert client.get(path).json()["publication_state"] == "UNPUBLISHED"
    assert client.get("/api/v1/public/openings").json()["items"] == []
    assert mutate(client, path, preview).status_code == 409
    assert mutate(client, path, client.get(path).json()).status_code == 200
    opening.refresh_from_db()
    opening = update_opening(opening=opening, membership=tenant_admin, changes={"state": "PAUSED"})
    assert mutate(client, path, client.get(path).json()).status_code == 422
    update_opening(opening=opening, membership=tenant_admin, changes={"state": "OPEN"})
    assert client.get(path).json()["publication_state"] == "UNPUBLISHED"


def test_publication_authorization_rechecked_before_replay(publication, tenant_admin):
    client, path, _ = publication
    preview = client.get(path).json()
    key = str(uuid.uuid4())
    assert mutate(client, path, preview, key=key).status_code == 200
    tenant_admin.scope = {"opening_ids": [str(uuid.uuid4())]}
    tenant_admin.save()
    assert mutate(client, path, preview, key=key).status_code in {403, 404}
    assert client.get(path).status_code in {403, 404}
    client.logout()
    assert client.get(path).status_code in {401, 403, 404}
    assert mutate(client, path, preview).status_code in {401, 403, 404}


def test_publication_audit_failure_rolls_back(publication):
    client, path, _ = publication
    preview = client.get(path).json()
    with patch(
        "modules.recruiting.public_openings.record_governance_event", side_effect=RuntimeError
    ):
        with pytest.raises(RuntimeError):
            mutate(client, path, preview)
    assert not PublicOpeningProjection.objects.exists()


def test_publication_audit_is_value_minimized(publication):
    from modules.audit.models import AuditEvent

    client, path, opening = publication
    assert mutate(client, path, client.get(path).json()).status_code == 200
    assert mutate(client, path, client.get(path).json(), "withdraw").status_code == 200
    events = AuditEvent.objects.filter(
        action__in=["OPENING_PUBLISHED", "OPENING_PUBLICATION_WITHDRAWN"]
    )
    assert events.count() == 2
    for event in events:
        assert opening.title not in str(event.metadata)
        assert "preview_digest" not in event.metadata


@pytest.mark.parametrize("role", ["HIRING_MANAGER", "PLATFORM_SECURITY_ADMIN", "CANDIDATE"])
def test_non_management_roles_cannot_publish(publication, tenant_admin, role):
    client, path, _ = publication
    preview = client.get(path).json()
    # Invalid tenant roles are assigned only in this negative authorization fixture.
    tenant_admin.role = role
    tenant_admin.save()
    assert client.get(path).status_code in {403, 404}
    assert mutate(client, path, preview).status_code in {403, 404}
    assert mutate(client, path, preview, "withdraw").status_code in {403, 404}


def test_cross_tenant_and_cross_opening_digest_denied(publication, tenant, opening_factory):
    from tests.factories import TenantFactory

    client, path, opening = publication
    preview = client.get(path).json()
    other = opening_factory(tenant=TenantFactory())
    wrong = path.replace(str(opening.id), str(other.id))
    assert client.get(wrong).status_code == 404
    assert mutate(client, wrong, preview).status_code == 404
    own_other = opening_factory(tenant=tenant)
    own_path = path.replace(str(opening.id), str(own_other.id))
    own_preview = client.get(own_path).json()
    assert (
        mutate(client, own_path, own_preview, preview_digest=preview["preview_digest"]).status_code
        == 409
    )


def test_source_values_bound_even_without_version_change(publication):
    client, path, opening = publication
    preview = client.get(path).json()
    opening.description = "Changed after review"
    opening.save(update_fields=["description"])
    assert mutate(client, path, preview).status_code == 409


def test_inactive_unit_and_expired_projection_cannot_publish(publication):
    from datetime import timedelta

    from django.utils import timezone

    client, path, opening = publication
    assert mutate(client, path, client.get(path).json()).status_code == 200
    projection = PublicOpeningProjection.objects.get()
    projection.closes_at = timezone.now() - timedelta(seconds=1)
    projection.save()
    assert client.get(path).json()["publication_state"] == "UNPUBLISHED"
    assert mutate(client, path, client.get(path).json()).status_code == 422
    projection.closes_at = None
    projection.active = False
    projection.save()
    opening.business_unit.status = "ARCHIVED"
    opening.business_unit.save()
    assert mutate(client, path, client.get(path).json()).status_code == 422


def test_failed_sync_after_edit_cannot_reactivate_old_data(publication, tenant_admin):
    client, path, opening = publication
    assert mutate(client, path, client.get(path).json()).status_code == 200
    opening.refresh_from_db()
    update_opening(
        opening=opening, membership=tenant_admin, changes={"description": "Fresh review needed"}
    )
    preview = client.get(path).json()
    with patch(
        "modules.recruiting.public_openings.record_governance_event", side_effect=RuntimeError
    ):
        with pytest.raises(RuntimeError):
            mutate(client, path, preview)
    assert client.get("/api/v1/public/openings").json()["items"] == []


def test_missing_confirmation_and_anonymous_withdraw_denied(publication):
    client, path, _ = publication
    preview = client.get(path).json()
    response = client.post(
        f"{path}/publish",
        {"preview_digest": preview["preview_digest"]},
        format="json",
        HTTP_IF_MATCH=preview["source_etag"],
        HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
    )
    assert response.status_code == 422
    assert mutate(client, path, preview, "withdraw", confirmed=False).status_code == 422
    client.logout()
    assert mutate(client, path, preview, "withdraw").status_code in {401, 403, 404}
