import pytest

from modules.recruiting.models import OpeningPublicationLink
from tests.database.test_public_opening_projection import publish

pytestmark = [pytest.mark.django_db, pytest.mark.postgres]


def test_public_jobs_flag_is_independent_default_off_and_reversible(
    client, opening_factory, recruiter, settings
):
    opening = opening_factory(tenant=recruiter.tenant, state="DRAFT")
    publish(opening, recruiter)

    settings.FRONTEND_REACT_ROUTES = {}
    legacy = client.get("/jobs/")
    assert legacy.status_code == 200
    assert b"Open roles" in legacy.content
    assert b"data-react-page" not in legacy.content

    settings.FRONTEND_REACT_ROUTES = {"public-jobs-page": True}
    react = client.get("/jobs/")
    assert react.status_code == 200
    assert b'data-frontend-renderer="react"' in react.content
    assert b'"page": "public-jobs"' in react.content
    assert str(opening.tenant_id).encode() not in react.content
    assert b"data-react-page" in react.content
    assert opening.title.encode() not in react.content
    assert "no-store" in react["Cache-Control"]

    settings.FRONTEND_REACT_ROUTES = {}
    assert b"Open roles" in client.get("/jobs/").content


def test_public_role_flag_allows_signed_out_read_without_candidate_identifiers(
    client, opening_factory, recruiter, settings
):
    opening = opening_factory(tenant=recruiter.tenant, state="DRAFT")
    publish(opening, recruiter)
    public_id = OpeningPublicationLink.objects.get(opening=opening).public_id
    path = f"/roles/{public_id}/"

    settings.FRONTEND_REACT_ROUTES = {}
    legacy = client.get(path)
    assert legacy.status_code == 200
    assert b"data-application-page" in legacy.content

    settings.FRONTEND_REACT_ROUTES = {"public-role-page": True}
    react = client.get(path)
    assert react.status_code == 200
    assert b'data-frontend-renderer="react"' in react.content
    assert b'"page": "public-role"' in react.content
    assert str(public_id).encode() in react.content
    assert b'"resumeId"' not in react.content
    assert b'"consentId"' not in react.content
    assert b"data-application-page" not in react.content
    assert "no-store" in react["Cache-Control"]

    settings.FRONTEND_REACT_ROUTES = {}
    assert b"data-application-page" in client.get(path).content


def test_unpublished_role_stays_unavailable_with_react_flag(
    client, opening_factory, tenant, settings
):
    opening = opening_factory(tenant=tenant, state="DRAFT")
    settings.FRONTEND_REACT_ROUTES = {"public-role-page": True}

    assert client.get(f"/roles/{opening.id}/").status_code == 404
