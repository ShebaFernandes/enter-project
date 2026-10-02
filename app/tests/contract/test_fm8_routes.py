import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.postgres]


def test_comparison_flag_is_independent_default_off_and_reversible(client, recruiter, settings):
    client.force_login(recruiter.identity)
    path = f"/tenants/{recruiter.tenant_id}/recruiter/comparison/"

    settings.FRONTEND_REACT_ROUTES = {}
    assert b"data-comparison" in client.get(path).content

    settings.FRONTEND_REACT_ROUTES = {"recruiter-comparison-page": True}
    response = client.get(path)
    assert b'data-frontend-renderer="react"' in response.content
    assert b'"page": "candidate-comparison"' in response.content
    assert str(recruiter.tenant_id).encode() in response.content
    assert b"data-comparison" not in response.content
    assert "no-store" in response["Cache-Control"]

    settings.FRONTEND_REACT_ROUTES = {}
    assert b"data-comparison" in client.get(path).content

    recruiter.role = "TENANT_ADMIN"
    recruiter.save()
    settings.FRONTEND_REACT_ROUTES = {"recruiter-comparison-page": True}
    assert client.get(path).status_code == 403
