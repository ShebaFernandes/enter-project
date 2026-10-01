import uuid

import pytest

from modules.recruiting.models import OpeningPublicationLink
from tests.database.test_public_opening_projection import publish

pytestmark = pytest.mark.django_db


def test_public_directory_allowlist_pagination_and_detail(
    api_client, opening_factory, tenant, recruiter
):
    for _ in range(3):
        publish(opening_factory(tenant=tenant, state="DRAFT"), recruiter)
    opening_factory(tenant=tenant, state="DRAFT")
    response = api_client.get("/api/v1/public/openings?limit=2")
    assert response.status_code == 200
    assert response["Cache-Control"] == "no-store"
    assert len(response.data["items"]) == 2
    row = response.data["items"][0]
    assert set(row) == {
        "id",
        "title",
        "description",
        "location",
        "work_mode",
        "employment_type",
        "published_at",
        "closes_at",
        "application_url",
    }
    assert api_client.get(f"/api/v1/public/openings/{row['id']}").data == row
    following = api_client.get(
        f"/api/v1/public/openings?limit=2&cursor={response.data['next_cursor']}"
    )
    assert len(following.data["items"]) == 1
    assert following.data["next_cursor"] is None
    for link in OpeningPublicationLink.objects.all():
        assert str(link.opening_id) not in str(response.data)
        assert api_client.get(f"/api/v1/public/openings/{link.opening_id}").status_code == 404
    assert str(tenant.id) not in str(response.data)


def test_public_bad_pagination_and_non_enumeration(api_client, opening_factory, tenant):
    draft = opening_factory(tenant=tenant, state="DRAFT")
    for query in ("limit=0", "limit=101", "limit=no", "cursor=bad"):
        assert api_client.get(f"/api/v1/public/openings?{query}").status_code == 422
    absent = api_client.get(f"/api/v1/public/openings/{uuid.uuid4()}")
    hidden = api_client.get(f"/api/v1/public/openings/{draft.id}")
    assert absent.status_code == hidden.status_code == 404
    assert absent.data == hidden.data


def test_public_rate_limit_and_no_mutation(api_client):
    for _ in range(60):
        assert api_client.get("/api/v1/public/openings").status_code == 200
    response = api_client.get("/api/v1/public/openings")
    assert response.status_code == 429
    assert "Retry-After" in response


def test_signed_out_entry_and_jobs_legacy_default(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b'data-frontend-renderer="legacy"' in response.content
    assert b'href="/api/v1/auth/login"' in response.content
    assert b'href="/jobs/"' in response.content
    assert client.get("/jobs/").status_code == 200


def test_public_dependency_failure_is_safe_and_fails_closed(api_client):
    from unittest.mock import patch

    from django.db import OperationalError

    with patch(
        "modules.recruiting.public_views.available_publications",
        side_effect=OperationalError("private diagnostic"),
    ):
        response = api_client.get("/api/v1/public/openings")
    assert response.status_code == 503
    assert b"private diagnostic" not in response.content
    assert response["Cache-Control"] == "no-store"
    with patch(
        "modules.recruiting.public_views.PublicOpeningThrottle.cache.get",
        side_effect=ConnectionError("private diagnostic"),
    ):
        response = api_client.get("/api/v1/public/openings")
    assert response.status_code == 503
    assert b"private diagnostic" not in response.content


def test_public_projection_api_rejects_writes(api_client):
    for method in (api_client.post, api_client.put, api_client.patch, api_client.delete):
        assert method("/api/v1/public/openings", {}, format="json").status_code == 405
