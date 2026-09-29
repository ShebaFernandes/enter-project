from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from modules.identity.models import Identity, IdentityCapability
from modules.tenancy.grants import (
    approve_emergency_access,
    request_emergency_access,
    revalidate_emergency_access,
    revoke_emergency_access,
)

pytestmark = pytest.mark.django_db


def make_admin(subject, assigned_by=None):
    identity = Identity.objects.create_user(
        cognito_subject=subject,
        email_lookup_hmac=f"hmac-{subject}".encode(),
        email_ciphertext=f"cipher-{subject}".encode(),
    )
    IdentityCapability.objects.create(
        identity=identity,
        role=IdentityCapability.Role.PLATFORM_SECURITY_ADMIN,
        assigned_by=assigned_by or identity,
    )
    return identity


def test_break_glass_scope_independent_approval_expiry_and_revocation(tenant):
    requester = make_admin("requester")
    approver = make_admin("approver", assigned_by=requester)
    with pytest.raises(ValidationError):
        request_emergency_access(
            requester=requester,
            tenant=tenant,
            reason_code="INCIDENT",
            reason="Synthetic incident investigation",
            incident_reference="INC-001",
            object_scope={"ids": ["object-1"]},
            field_scope=[],
            operation_scope=["READ"],
            requested_minutes=30,
        )
    access = request_emergency_access(
        requester=requester,
        tenant=tenant,
        reason_code="INCIDENT",
        reason="Synthetic incident investigation",
        incident_reference="INC-001",
        object_scope={"ids": ["object-1"]},
        field_scope=["profile_state"],
        operation_scope=["READ"],
        requested_minutes=30,
    )
    with pytest.raises(ValidationError):
        approve_emergency_access(request=access, approver=requester)
    approve_emergency_access(request=access, approver=approver)
    assert access.expires_at <= timezone.now() + timedelta(hours=1)
    revalidate_emergency_access(
        request=access,
        actor=requester,
        tenant_id=tenant.id,
        object_id="object-1",
        fields={"profile_state"},
    )
    with pytest.raises(ValidationError):
        revalidate_emergency_access(
            request=access,
            actor=requester,
            tenant_id=tenant.id,
            object_id="object-1",
            fields={"email"},
        )
    revoke_emergency_access(request=access, actor=approver)
    assert access.status == access.Status.REVOKED
