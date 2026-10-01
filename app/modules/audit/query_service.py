from __future__ import annotations

from django.core.exceptions import PermissionDenied, ValidationError

from modules.tenancy.models import TenantMembership
from modules.tenancy.policy import AuthorizationRequest, authorize

from .models import AuditEvent
from .service import record_audit_event


def _record_read(*, membership, tenant_id, outcome: str, result_count: int = 0) -> None:
    record_audit_event(
        actor=membership.identity,
        effective_role=membership.role,
        tenant_id=tenant_id,
        action="AUDIT_READ",
        target_type="audit_event",
        target_id="",
        purpose_code="SECURITY_GOVERNANCE",
        outcome=outcome,
        metadata={
            "query_scope": "TENANT_ADMIN_METADATA"
            if membership.role == TenantMembership.Role.TENANT_ADMIN
            else "OWN_ACTIVITY",
            "result_count_band": "0"
            if result_count == 0
            else ("1-25" if result_count <= 25 else "26-100"),
        },
    )


def _summary(event: AuditEvent) -> dict:
    return {
        "id": str(event.id),
        "occurred_at": event.occurred_at.isoformat(),
        "actor_id": str(event.actor_id) if event.actor_id else None,
        "effective_role": str(event.metadata.get("effective_role", "")),
        "action": event.action,
        "target_type": event.target_type,
        "outcome": event.outcome,
        "reason_code": event.metadata.get("reason_code") or None,
        "correlation_id": event.metadata.get("correlation_id") or None,
    }


def query_audit_events(*, membership, tenant_id, limit: int = 100) -> list[dict]:
    if membership.tenant_id != tenant_id:
        _record_read(membership=membership, tenant_id=tenant_id, outcome="DENIED")
        raise PermissionDenied("Audit history unavailable")
    if not 1 <= limit <= 100:
        _record_read(membership=membership, tenant_id=tenant_id, outcome="FAILED")
        raise ValidationError({"limit": "Limit must be between 1 and 100."})
    try:
        authorize(
            AuthorizationRequest(
                action="audit.read",
                role=membership.role,
                tenant_id=membership.tenant_id,
                object_tenant_id=tenant_id,
                actor=membership.identity,
            )
        )
    except PermissionDenied:
        _record_read(membership=membership, tenant_id=tenant_id, outcome="DENIED")
        raise
    queryset = AuditEvent.objects.filter(tenant_id=tenant_id).exclude(action="AUDIT_READ")
    if membership.role in {
        TenantMembership.Role.RECRUITER,
        TenantMembership.Role.HIRING_MANAGER,
    }:
        queryset = queryset.filter(actor=membership.identity)
    elif membership.role != TenantMembership.Role.TENANT_ADMIN:
        _record_read(membership=membership, tenant_id=tenant_id, outcome="DENIED")
        raise PermissionDenied("Audit history unavailable")
    events = list(queryset.order_by("-occurred_at", "-id")[:limit])
    result = [_summary(event) for event in events]
    _record_read(
        membership=membership,
        tenant_id=tenant_id,
        outcome="ALLOWED",
        result_count=len(result),
    )
    return result
