import uuid

import pytest

from tests.factories import MembershipFactory

pytestmark = [pytest.mark.django_db, pytest.mark.postgres]


def test_governance_flag_is_default_off_and_reversible(client, tenant, settings):
    admin = MembershipFactory(tenant=tenant, tenant_admin=True)
    client.force_login(admin.identity)
    path = f"/tenants/{tenant.id}/admin/governance/"

    settings.FRONTEND_REACT_ROUTES = {}
    legacy = client.get(path)
    assert legacy.status_code == 200
    assert b"data-governance" in legacy.content
    assert b"data-react-page" not in legacy.content

    settings.FRONTEND_REACT_ROUTES = {"tenant-governance-page": True}
    react = client.get(path)
    assert react.status_code == 200
    assert b'data-frontend-renderer="react"' in react.content
    assert b'"page": "tenant-governance"' in react.content
    assert str(tenant.id).encode() in react.content
    assert b'"requiresSession": true' in react.content
    assert b"data-governance" not in react.content
    assert "no-store" in react["Cache-Control"]

    settings.FRONTEND_REACT_ROUTES = {}
    assert b"data-governance" in client.get(path).content


def test_governance_react_route_keeps_role_and_tenant_boundary(client, recruiter, settings):
    client.force_login(recruiter.identity)
    settings.FRONTEND_REACT_ROUTES = {"tenant-governance-page": True}

    assert client.get(f"/tenants/{recruiter.tenant_id}/admin/governance/").status_code == 403
    assert client.get(f"/tenants/{uuid.uuid4()}/admin/governance/").status_code == 403
