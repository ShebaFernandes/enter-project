import uuid

import pytest
from rest_framework.test import APIClient

from modules.identity.models import IdentityCapability

pytestmark = pytest.mark.django_db


def test_candidate_session_and_global_signout(identity):
    IdentityCapability.objects.create(
        identity=identity,
        role=IdentityCapability.Role.CANDIDATE,
        assigned_by=identity,
    )
    client = APIClient()
    client.force_login(identity)
    response = client.get("/api/v1/session")
    assert response.status_code == 200
    assert response.json()["role"] == "CANDIDATE"
    assert response["X-Request-ID"]
    assert response["Content-Security-Policy"]
    assert client.delete("/api/v1/session/sign-out").status_code == 204


def test_sign_in_endpoint_exposes_rate_limit_headers():
    response = APIClient().get("/api/v1/auth/login", REMOTE_ADDR="192.0.2.40")
    assert response.status_code == 302
    assert int(response["X-RateLimit-Remaining"]) >= 0


def test_invalid_tenant_context_is_non_enumerating(identity):
    client = APIClient()
    client.force_login(identity)
    response = client.get(
        "/api/v1/session",
        HTTP_X_TENANT_ID=str(uuid.uuid4()),
        HTTP_X_REQUEST_ID="synthetic-request",
    )
    assert response.status_code == 404
    assert response["Content-Type"].startswith("application/problem+json")
    assert response.json()["request_id"] == "synthetic-request"


def test_suspended_identity_revokes_existing_session(identity):
    client = APIClient()
    client.force_login(identity)
    identity.status = identity.Status.SUSPENDED
    identity.save(update_fields=("status",))
    response = client.get("/api/v1/session")
    assert response.status_code == 401
    assert response["Content-Type"].startswith("application/problem+json")


def test_business_unit_create_is_tenant_scoped_and_idempotent(recruiter, tenant):
    client = APIClient()
    client.force_login(recruiter.identity)
    headers = {
        "HTTP_X_TENANT_ID": str(tenant.id),
        "HTTP_IDEMPOTENCY_KEY": "synthetic-unit-key-0001",
    }
    path = f"/api/v1/tenants/{tenant.id}/business-units"
    first = client.post(path, {"name": "Synthetic Product"}, format="json", **headers)
    replay = client.post(path, {"name": "Synthetic Product"}, format="json", **headers)
    assert first.status_code == 201
    assert replay.status_code == 201
    assert replay.json()["id"] == first.json()["id"]


def test_platform_tenant_provisioning_requires_global_security_role(identity):
    client = APIClient()
    client.force_login(identity)
    response = client.post(
        "/api/v1/platform/tenants",
        {
            "contracted_company_name": "Denied Synthetic Company",
            "legal_boundary_reference": "denied-contract",
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY="synthetic-tenant-key-01",
    )
    assert response.status_code == 404
