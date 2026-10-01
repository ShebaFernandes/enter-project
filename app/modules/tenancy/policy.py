from __future__ import annotations

from dataclasses import dataclass

from django.core.exceptions import PermissionDenied
from django.utils import timezone

from modules.audit.service import record_audit_event

from .models import AccessGrant, EmergencyAccessRequest, TenantMembership


@dataclass(frozen=True)
class AuthorizationRequest:
    action: str
    role: str
    tenant_id: object | None
    object_tenant_id: object | None = None
    purpose: str | None = None
    fields: frozenset[str] = frozenset()
    object_id: str | None = None
    consent_purposes: frozenset[str] = frozenset()
    consent_fields: frozenset[str] = frozenset()
    grant: AccessGrant | None = None
    emergency_request: EmergencyAccessRequest | None = None
    actor: object | None = None
    sensitive: bool = False


ROLE_ACTIONS: dict[str, frozenset[str]] = {
    "CANDIDATE": frozenset(
        {"own.read", "own.write", "rights.use", "resume.own.read", "application.own"}
    ),
    TenantMembership.Role.RECRUITER: frozenset(
        {
            "business_unit.read",
            "business_unit.write",
            "opening.read",
            "opening.write",
            "candidate.search",
            "candidate.read",
            "candidate.field.read",
            "candidate.compare",
            "recruiter_candidate.create",
            "recruiter_candidate.read",
            "application.read",
            "application.status.write",
            "application.status.publish",
            "candidate_work.read",
            "candidate_work.write",
            "recruiter_note.read",
            "recruiter_note.write",
            "shortlist.write",
            "candidate.disclosure.preview",
            "candidate.disclosure.confirm",
        }
    ),
    TenantMembership.Role.HIRING_MANAGER: frozenset(
        {
            "opening.read",
            "candidate.search",
            "candidate.read",
            "candidate.field.read",
            "candidate.compare",
            "recruiter_candidate.read",
            "application.read",
            "application.status.write",
            "application.status.publish",
            "candidate_work.read",
            "candidate_work.write",
            "recruiter_note.read",
            "recruiter_note.write",
            "shortlist.write",
            "candidate.disclosure.preview",
            "candidate.disclosure.confirm",
        }
    ),
    TenantMembership.Role.TENANT_ADMIN: frozenset(
        {
            "business_unit.read",
            "business_unit.write",
            "opening.read",
            "opening.write",
            "tenant.admin",
        }
    ),
    "PLATFORM_SECURITY_ADMIN": frozenset({"platform.tenant.provision", "security.admin"}),
}


def authorize(check: AuthorizationRequest) -> None:
    try:
        if check.action not in ROLE_ACTIONS.get(check.role, frozenset()):
            raise PermissionDenied("Operation unavailable")
        if check.object_tenant_id is not None and check.tenant_id != check.object_tenant_id:
            raise PermissionDenied("Operation unavailable")
        if check.sensitive:
            _authorize_sensitive(check)
    except PermissionDenied:
        if check.actor is not None:
            record_audit_event(
                actor=check.actor,
                tenant_id=check.tenant_id,
                action=check.action,
                target_type="authorization_target",
                target_id=check.object_id or "",
                outcome="DENIED",
                reason_code="POLICY_DENIED",
                metadata={"requested_fields": sorted(check.fields)},
            )
        raise


def _authorize_sensitive(check: AuthorizationRequest) -> None:
    if not check.purpose or check.purpose not in check.consent_purposes:
        raise PermissionDenied("Operation unavailable")
    if not check.fields or not check.fields.issubset(check.consent_fields):
        raise PermissionDenied("Operation unavailable")
    if check.grant is None:
        if check.emergency_request is not None:
            _authorize_emergency(check)
            return
        raise PermissionDenied("Operation unavailable")
    grant = check.grant
    now = timezone.now()
    if (
        grant.status != AccessGrant.Status.ACTIVE
        or grant.valid_from > now
        or grant.expires_at <= now
        or grant.tenant_id != check.tenant_id
        or grant.purpose_code != check.purpose
        or not check.fields.issubset(set(grant.field_scope))
        or check.object_id not in {str(value) for value in grant.object_scope.get("ids", [])}
        or (check.actor is not None and grant.grantee_id != getattr(check.actor, "pk", None))
    ):
        raise PermissionDenied("Operation unavailable")


def _authorize_emergency(check: AuthorizationRequest) -> None:
    request = check.emergency_request
    if request is None:
        raise PermissionDenied("Operation unavailable")
    if (
        request.status != EmergencyAccessRequest.Status.ACTIVE
        or request.expires_at is None
        or request.expires_at <= timezone.now()
        or request.tenant_id != check.tenant_id
        or "READ" not in request.operation_scope
        or not check.fields.issubset(set(request.field_scope))
        or check.object_id not in {str(value) for value in request.object_scope.get("ids", [])}
        or (check.actor is not None and request.requester_id != getattr(check.actor, "pk", None))
    ):
        raise PermissionDenied("Operation unavailable")


def authorize_opening(membership: TenantMembership, opening, action: str) -> None:
    authorize(
        AuthorizationRequest(
            action=action,
            role=membership.role,
            tenant_id=membership.tenant_id,
            object_tenant_id=opening.tenant_id,
        )
    )
    opening_ids = {str(value) for value in membership.scope.get("opening_ids", [])}
    unit_ids = {str(value) for value in membership.scope.get("business_unit_ids", [])}
    if opening_ids and str(opening.id) not in opening_ids:
        raise PermissionDenied("Operation unavailable")
    if unit_ids and str(opening.business_unit_id) not in unit_ids:
        raise PermissionDenied("Operation unavailable")
    if (
        membership.role == TenantMembership.Role.HIRING_MANAGER
        and not opening.hiring_team.filter(membership=membership).exists()
    ):
        raise PermissionDenied("Operation unavailable")
