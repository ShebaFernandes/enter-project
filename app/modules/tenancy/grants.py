from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from modules.audit.service import record_audit_event
from modules.identity.models import IdentityCapability

from .models import EmergencyAccessRequest


def _is_security_admin(identity) -> bool:
    return identity.capabilities.filter(
        role=IdentityCapability.Role.PLATFORM_SECURITY_ADMIN, revoked_at__isnull=True
    ).exists()


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
    request.approver = approver
    request.approved_at = timezone.now()
    request.expires_at = timezone.now() + timedelta(minutes=min(request.requested_minutes, 60))
    request.status = EmergencyAccessRequest.Status.ACTIVE
    request.full_clean()
    request.save()
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
    if actor.id not in {request.requester_id, request.approver_id} and not _is_security_admin(
        actor
    ):
        raise ValidationError("Revocation unavailable")
    request.status = EmergencyAccessRequest.Status.REVOKED
    request.revoked_by = actor
    request.revoked_at = timezone.now()
    request.save(update_fields=("status", "revoked_by", "revoked_at"))
    record_audit_event(
        actor=actor,
        effective_role="PLATFORM_SECURITY_ADMIN",
        tenant_id=request.tenant_id,
        action="EMERGENCY_ACCESS_REVOKE",
        target_type="emergency_access_request",
        target_id=str(request.id),
        outcome="ALLOWED",
        reason_code=request.reason_code,
    )
    return request
