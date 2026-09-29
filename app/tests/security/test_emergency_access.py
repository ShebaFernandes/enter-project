from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from modules.audit.models import AuditEvent
from modules.communications.models import Notification
from modules.identity.models import Identity, IdentityCapability
from modules.operations.crypto import encrypt
from modules.tenancy.grants import (
    approve_emergency_access,
    request_emergency_access,
    revalidate_emergency_access,
    revoke_emergency_access,
)
from modules.tenancy.models import TenantMembership

pytestmark = pytest.mark.django_db


def make_admin(subject, assigned_by=None):
    identity = Identity.objects.create_user(
        cognito_subject=subject,
        email_lookup_hmac=f"hmac-{subject}".encode(),
        email_ciphertext=encrypt(f"{subject}@synthetic.invalid"),
        email_verified_at=timezone.now(),
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
    tenant_admin = Identity.objects.create_user(
        cognito_subject="tenant-admin-notice",
        email_lookup_hmac=b"tenant-admin-notice-hmac",
        email_ciphertext=encrypt("tenant-admin@synthetic.invalid"),
        email_verified_at=timezone.now(),
    )
    TenantMembership.objects.create(
        tenant=tenant,
        identity=tenant_admin,
        role=TenantMembership.Role.TENANT_ADMIN,
        status=TenantMembership.Status.ACTIVE,
    )
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
    assert access.expires_at is not None
    assert access.expires_at <= timezone.now() + timedelta(hours=1)
    assert access.tenant_admin_notified_at is not None
    notice = Notification.objects.get(tenant_id=tenant.id)
    assert notice.template_key == "security-emergency-access-approved"
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
    access.expires_at = timezone.now() - timedelta(seconds=1)
    access.save(update_fields=("expires_at",))
    with pytest.raises(ValidationError):
        revalidate_emergency_access(
            request=access,
            actor=requester,
            tenant_id=tenant.id,
            object_id="object-1",
            fields={"profile_state"},
        )
    access.expires_at = timezone.now() + timedelta(minutes=5)
    access.save(update_fields=("expires_at",))
    revoke_emergency_access(request=access, actor=tenant_admin)
    assert access.status == access.Status.REVOKED
    with pytest.raises(ValidationError):
        revalidate_emergency_access(
            request=access,
            actor=requester,
            tenant_id=tenant.id,
            object_id="object-1",
            fields={"profile_state"},
        )
    assert (
        AuditEvent.objects.filter(
            target_id=str(access.id),
            action__in={
                "EMERGENCY_ACCESS_REQUEST",
                "EMERGENCY_ACCESS_APPROVE",
                "EMERGENCY_ACCESS_REVOKE",
            },
        ).count()
        == 3
    )


def test_break_glass_rejects_non_read_or_unscoped_requests(tenant):
    requester = make_admin("invalid-scope-requester")
    common = {
        "requester": requester,
        "tenant": tenant,
        "reason_code": "INCIDENT",
        "reason": "Synthetic incident investigation",
        "incident_reference": "INC-002",
        "field_scope": ["profile_state"],
        "requested_minutes": 30,
    }
    with pytest.raises(ValidationError):
        request_emergency_access(
            **common,
            object_scope={},
            operation_scope=["READ"],
        )
    with pytest.raises(ValidationError):
        request_emergency_access(
            **common,
            object_scope={"ids": ["object-1"]},
            operation_scope=["WRITE"],
        )
