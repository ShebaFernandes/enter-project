import uuid

import pytest

from tests.factories import MembershipFactory

pytestmark = [pytest.mark.django_db, pytest.mark.postgres]


def test_organization_flag_is_default_off_and_reversible(client, recruiter, settings):
    client.force_login(recruiter.identity)
    path = f"/tenants/{recruiter.tenant_id}/recruiter/organization/"

    settings.FRONTEND_REACT_ROUTES = {}
    legacy = client.get(path)
    assert legacy.status_code == 200
    assert b"data-organization" in legacy.content
    assert b"data-react-page" not in legacy.content

    settings.FRONTEND_REACT_ROUTES = {"recruiter-organization-page": True}
    react = client.get(path)
    assert react.status_code == 200
    assert b'data-frontend-renderer="react"' in react.content
    assert b'"page": "recruiter-organization"' in react.content
    assert str(recruiter.tenant_id).encode() in react.content
    assert b'"requiresSession": true' in react.content
    assert b"data-organization" not in react.content
    assert "no-store" in react["Cache-Control"]

    settings.FRONTEND_REACT_ROUTES = {}
    assert b"data-organization" in client.get(path).content


def test_organization_react_route_keeps_role_and_tenant_boundary(client, tenant, settings):
    admin = MembershipFactory(tenant=tenant, tenant_admin=True)
    client.force_login(admin.identity)
    settings.FRONTEND_REACT_ROUTES = {"recruiter-organization-page": True}

    assert client.get(f"/tenants/{tenant.id}/recruiter/organization/").status_code == 403
    assert client.get(f"/tenants/{uuid.uuid4()}/recruiter/organization/").status_code == 403
