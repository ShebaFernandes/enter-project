import uuid

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.postgres]


def test_results_flag_is_independent_and_rolls_back(client, recruiter, settings):
    client.force_login(recruiter.identity)
    path = f"/tenants/{recruiter.tenant_id}/recruiter/search/"
    settings.FRONTEND_REACT_ROUTES = {"recruiter-search-page": True}
    assert b'data-frontend-renderer="legacy"' in client.get(path + "?view=results").content
    settings.FRONTEND_REACT_ROUTES = {"recruiter-results-page": True}
    response = client.get(path + "?view=results")
    assert b'data-frontend-renderer="react"' in response.content
    assert b'"page": "search-results"' in response.content
    assert b"data-recruiter-search" not in response.content
    assert "no-store" in response["Cache-Control"]
    assert b'data-frontend-renderer="legacy"' in client.get(path).content
    settings.FRONTEND_REACT_ROUTES = {}
    assert b'data-frontend-renderer="legacy"' in client.get(path + "?view=results").content
    recruiter.role = "TENANT_ADMIN"
    recruiter.save()
    settings.FRONTEND_REACT_ROUTES = {"recruiter-results-page": True}
    assert client.get(path + "?view=results").status_code == 403


def test_candidate_shared_route_remains_legacy_until_fm7(client, recruiter, settings):
    client.force_login(recruiter.identity)
    settings.FRONTEND_REACT_ROUTES = {"recruiter-candidate-page": True}
    response = client.get(f"/tenants/{recruiter.tenant_id}/recruiter/candidates/{uuid.uuid4()}/")
    assert b'data-frontend-renderer="legacy"' in response.content
    assert b"data-candidate-management" in response.content
