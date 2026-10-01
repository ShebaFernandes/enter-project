import uuid

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.postgres]


def test_management_flag_is_independent_default_off_and_reversible(client, recruiter, settings):
    client.force_login(recruiter.identity)
    candidate = uuid.uuid4()
    path = f"/tenants/{recruiter.tenant_id}/recruiter/candidates/{candidate}/"
    settings.FRONTEND_REACT_ROUTES = {}
    assert b"data-candidate-management" in client.get(path).content
    settings.FRONTEND_REACT_ROUTES = {"recruiter-candidate-management-page": True}
    response = client.get(path)
    assert b'data-frontend-renderer="react"' in response.content
    assert b'"page": "candidate-management"' in response.content
    assert str(candidate).encode() in response.content
    assert b"data-candidate-management" not in response.content
    assert "no-store" in response["Cache-Control"]
    settings.FRONTEND_REACT_ROUTES = {}
    assert b"data-candidate-management" in client.get(path).content
    recruiter.role = "TENANT_ADMIN"
    recruiter.save()
    settings.FRONTEND_REACT_ROUTES = {"recruiter-candidate-management-page": True}
    assert client.get(path).status_code == 403
