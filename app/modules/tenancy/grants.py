from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from modules.audit.service import record_audit_event
from modules.communications.models import Notification
from modules.communications.service import queue_notification
from modules.identity.models import IdentityCapability
from modules.operations.crypto import decrypt

from .models import AccessGrant, EmergencyAccessRequest, TenantMembership


def _is_security_admin(identity) -> bool:
    return identity.capabilities.filter(
        role=IdentityCapability.Role.PLATFORM_SECURITY_ADMIN, revoked_at__isnull=True
    ).exists()


@transaction.atomic
def create_access_grant(
    *,
    tenant,
    grantee,
    purpose_code: str,
    field_scope: list[str],
    object_scope: dict,
    valid_from,
    expires_at,
    actor,
) -> AccessGrant:
    grant = AccessGrant(
        tenant=tenant,
        grantee=grantee,
        purpose_code=purpose_code,
        field_scope=field_scope,
        object_scope=object_scope,
        valid_from=valid_from,
        expires_at=expires_at,
    )
    grant.full_clean()
    grant.save()
    record_audit_event(
        actor=actor,
        effective_role="TENANT_ADMIN",
        tenant_id=tenant.id,
        action="ACCESS_GRANT_CREATE",
        target_type="access_grant",
        target_id=str(grant.id),
        outcome="ALLOWED",
        metadata={"field_scope": field_scope, "purpose_code": purpose_code},
    )
    return grant


@transaction.atomic
def request_emergency_access(
    *,
    requester,
    tenant,
    reason_code: str,
    reason: str,
    incident_reference: str,
    object_scope: dict,
    field_scope: list[str],
    operation_scope: list[str],
    requested_minutes: int,
) -> EmergencyAccessRequest:
    if not _is_security_admin(requester):
        raise ValidationError("Platform Security Admin capability required")
    access_request = EmergencyAccessRequest(
        requester=requester,
        tenant=tenant,
        reason_code=reason_code,
        reason=reason,
        incident_reference=incident_reference,
        object_scope=object_scope,
        field_scope=field_scope,
        operation_scope=operation_scope,
        requested_minutes=requested_minutes,
    )
    access_request.full_clean()
    access_request.save()
    record_audit_event(
        actor=requester,
        effective_role="PLATFORM_SECURITY_ADMIN",
        tenant_id=tenant.id,
        action="EMERGENCY_ACCESS_REQUEST",
        target_type="emergency_access_request",
        target_id=str(access_request.id),
        outcome="ALLOWED",
        reason_code=reason_code,
    )
    return access_request


@transaction.atomic
def approve_emergency_access(
    *, request: EmergencyAccessRequest, approver
) -> EmergencyAccessRequest:
    if not _is_security_admin(approver):
        raise ValidationError("Platform Security Admin capability required")
    if request.requester_id == approver.id:
        raise ValidationError("Requester cannot self-approve")
    if request.status != EmergencyAccessRequest.Status.REQUESTED:
        raise ValidationError("Only a pending request can be approved")
    if not request.field_scope:
        raise ValidationError("field_scope is required")
    tenant_admins = list(
        TenantMembership.objects.select_related("identity").filter(
            tenant=request.tenant,
            role=TenantMembership.Role.TENANT_ADMIN,
            status=TenantMembership.Status.ACTIVE,
        )
    )
    if not tenant_admins:
        raise ValidationError("An active Tenant Admin is required for immediate notification")
    request.approver = approver
    request.approved_at = timezone.now()
    request.expires_at = timezone.now() + timedelta(minutes=min(request.requested_minutes, 60))
    request.status = EmergencyAccessRequest.Status.ACTIVE
    request.tenant_admin_notified_at = timezone.now()
    request.full_clean()
    request.save()
    for membership in tenant_admins:
        queue_notification(
            destination=decrypt(bytes(membership.identity.email_ciphertext)),
            channel=Notification.Channel.EMAIL,
            template_key="security-emergency-access-approved",
            template_version="v1",
            consent_basis="SECURITY_REQUIRED",
            idempotency_key=f"emergency-access:{request.id}:tenant-admin:{membership.id}",
            tenant_id=request.tenant_id,
        )
    record_audit_event(
        actor=approver,
        effective_role="PLATFORM_SECURITY_ADMIN",
        tenant_id=request.tenant_id,
        action="EMERGENCY_ACCESS_APPROVE",
        target_type="emergency_access_request",
        target_id=str(request.id),
        outcome="ALLOWED",
        reason_code=request.reason_code,
    )
    return request


def revalidate_emergency_access(
    *, request: EmergencyAccessRequest, actor, tenant_id, object_id: str, fields: set[str]
) -> None:
    allowed_ids = {str(value) for value in request.object_scope.get("ids", [])}
    if (
        request.requester_id != actor.id
        or request.tenant_id != tenant_id
        or request.status != EmergencyAccessRequest.Status.ACTIVE
        or request.expires_at is None
        or request.expires_at <= timezone.now()
        or "READ" not in request.operation_scope
        or not fields.issubset(set(request.field_scope))
        or str(object_id) not in allowed_ids
    ):
        raise ValidationError("Emergency access is unavailable")


@transaction.atomic
def revoke_emergency_access(*, request: EmergencyAccessRequest, actor) -> EmergencyAccessRequest:
    tenant_admin = TenantMembership.objects.filter(
        tenant=request.tenant,
        identity=actor,
        role=TenantMembership.Role.TENANT_ADMIN,
        status=TenantMembership.Status.ACTIVE,
    ).exists()
    if (
        actor.id not in {request.requester_id, request.approver_id}
        and not _is_security_admin(actor)
        and not tenant_admin
    ):
        raise ValidationError("Revocation unavailable")
    request.status = EmergencyAccessRequest.Status.REVOKED
    request.revoked_by = actor
    request.revoked_at = timezone.now()
    request.save(update_fields=("status", "revoked_by", "revoked_at"))
    record_audit_event(
        actor=actor,
        effective_role="TENANT_ADMIN" if tenant_admin else "PLATFORM_SECURITY_ADMIN",
        tenant_id=request.tenant_id,
        action="EMERGENCY_ACCESS_REVOKE",
        target_type="emergency_access_request",
        target_id=str(request.id),
        outcome="ALLOWED",
        reason_code=request.reason_code,
    )
    return request
