from __future__ import annotations

from dataclasses import dataclass

from django.core.exceptions import PermissionDenied

from .models import TenantMembership


@dataclass(frozen=True)
class AuthorizationRequest:
    action: str
    role: str
    tenant_id: object | None
    object_tenant_id: object | None = None
    purpose: str | None = None
    fields: frozenset[str] = frozenset()


ROLE_ACTIONS: dict[str, frozenset[str]] = {
    "CANDIDATE": frozenset({"own.read", "own.write"}),
    TenantMembership.Role.RECRUITER: frozenset(
        {"business_unit.read", "business_unit.write", "opening.read", "opening.write"}
    ),
    TenantMembership.Role.HIRING_MANAGER: frozenset({"opening.read"}),
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
    if check.action not in ROLE_ACTIONS.get(check.role, frozenset()):
        raise PermissionDenied("Operation unavailable")
    if check.object_tenant_id is not None and check.tenant_id != check.object_tenant_id:
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
