import uuid
from typing import cast

import pytest
from django.core.exceptions import PermissionDenied, ValidationError

from modules.audit.models import AuditEvent
from modules.audit.query_service import query_audit_events
from modules.audit.service import record_audit_event
from modules.identity.models import Identity
from tests.factories import MembershipFactory, TenantFactory

pytestmark = pytest.mark.django_db


def test_tenant_admin_reads_only_redacted_metadata_and_read_is_audited(api_client, tenant):
    admin = MembershipFactory(tenant=tenant, tenant_admin=True)
    record_audit_event(
        actor=cast(Identity, admin.identity),
        effective_role="TENANT_ADMIN",
        tenant_id=tenant.id,
        action="SYNTHETIC_ADMIN_ACTION",
        target_type="candidate_profile",
        target_id=str(uuid.uuid4()),
        outcome="ALLOWED",
        metadata={
            "candidate_name": "Synthetic Secret Name",
            "field_names": ["name", "contact"],
        },
    )
    api_client.force_login(admin.identity)
    response = api_client.get(
        f"/api/v1/tenants/{tenant.id}/audit-events",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert response.status_code == 200
    assert response.json()[0]["action"] == "SYNTHETIC_ADMIN_ACTION"
    serialized = str(response.json())
    assert "Synthetic Secret Name" not in serialized
    assert "metadata" not in serialized
    assert AuditEvent.objects.filter(
        tenant_id=tenant.id,
        actor=cast(Identity, admin.identity),
        action="AUDIT_READ",
        outcome="ALLOWED",
    ).exists()


def test_recruiter_audit_view_is_limited_to_own_activity(api_client, recruiter):
    other = MembershipFactory(tenant=recruiter.tenant, recruiter=True)
    record_audit_event(
        actor=recruiter.identity,
        tenant_id=recruiter.tenant_id,
        action="OWN_SYNTHETIC_ACTION",
        target_type="search",
        target_id=str(uuid.uuid4()),
        outcome="ALLOWED",
    )
    record_audit_event(
        actor=other.identity,
        tenant_id=recruiter.tenant_id,
        action="OTHER_SYNTHETIC_ACTION",
        target_type="search",
        target_id=str(uuid.uuid4()),
        outcome="ALLOWED",
    )
    api_client.force_login(recruiter.identity)
    response = api_client.get(
        f"/api/v1/tenants/{recruiter.tenant_id}/audit-events",
        HTTP_X_TENANT_ID=str(recruiter.tenant_id),
    )
    assert response.status_code == 200
    actions = {item["action"] for item in response.json()}
    assert "OWN_SYNTHETIC_ACTION" in actions
    assert "OTHER_SYNTHETIC_ACTION" not in actions


def test_denied_and_failed_audit_reads_are_audited_without_enumeration(tenant, recruiter):
    other_tenant = TenantFactory()
    with pytest.raises(PermissionDenied):
        query_audit_events(membership=recruiter, tenant_id=other_tenant.id)
    assert AuditEvent.objects.filter(
        actor=recruiter.identity,
        tenant_id=other_tenant.id,
        action="AUDIT_READ",
        outcome="DENIED",
    ).exists()

    with pytest.raises(ValidationError):
        query_audit_events(membership=recruiter, tenant_id=tenant.id, limit=0)
    failed = AuditEvent.objects.get(
        actor=recruiter.identity,
        tenant_id=tenant.id,
        action="AUDIT_READ",
        outcome="FAILED",
    )
    assert failed.target_id == ""
    assert "candidate" not in str(failed.metadata).casefold()


def test_tenant_admin_has_no_automatic_candidate_content_access(
    api_client, tenant, profile_factory
):
    admin = MembershipFactory(tenant=tenant, tenant_admin=True)
    profile = profile_factory(published=True)
    api_client.force_login(admin.identity)
    response = api_client.get(
        f"/api/v1/tenants/{tenant.id}/candidates/{profile.id}",
        {"search_id": str(uuid.uuid4())},
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert response.status_code in {403, 404}
    assert str(profile.id) not in str(response.data)
