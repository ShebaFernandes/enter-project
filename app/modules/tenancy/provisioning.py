from django.db import transaction
from django.utils.text import slugify

from modules.audit.service import record_audit_event
from modules.identity.models import IdentityCapability

from .models import Tenant


def _require_platform_onboarding(actor) -> None:
    if not actor.capabilities.filter(
        role=IdentityCapability.Role.PLATFORM_SECURITY_ADMIN, revoked_at__isnull=True
    ).exists():
        raise PermissionError("Platform onboarding authority required")


@transaction.atomic
def provision_tenant(
    *, actor, contracted_company_name: str, legal_boundary_reference: str
) -> Tenant:
    _require_platform_onboarding(actor)
    base = slugify(contracted_company_name)[:140] or "tenant"
    tenant = Tenant.objects.create(
        name=contracted_company_name.strip(),
        slug=base,
        legal_boundary_reference=legal_boundary_reference.strip(),
        status=Tenant.Status.ACTIVE,
    )
    record_audit_event(
        actor=actor,
        effective_role="PLATFORM_SECURITY_ADMIN",
        action="TENANT_PROVISION",
        target_type="tenant",
        target_id=str(tenant.id),
        outcome="ALLOWED",
        reason_code="PLATFORM_ONBOARDING",
    )
    return tenant


@transaction.atomic
def change_tenant_status(*, actor, tenant: Tenant, target_status: str) -> Tenant:
    _require_platform_onboarding(actor)
    target = Tenant.Status(target_status)
    allowed = {
        Tenant.Status.ACTIVE: {Tenant.Status.SUSPENDED, Tenant.Status.CLOSED},
        Tenant.Status.SUSPENDED: {Tenant.Status.ACTIVE, Tenant.Status.CLOSED},
    }
    current = Tenant.Status(tenant.status)
    if target not in allowed.get(current, set()):
        raise ValueError("Invalid tenant lifecycle transition")
    tenant.status = target
    tenant.version += 1
    tenant.save(update_fields=("status", "version"))
    record_audit_event(
        actor=actor,
        effective_role="PLATFORM_SECURITY_ADMIN",
        action="TENANT_STATUS_CHANGE",
        target_type="tenant",
        target_id=str(tenant.id),
        outcome="ALLOWED",
        reason_code=target,
    )
    return tenant


def merge_tenants(*, actor, **_kwargs) -> None:
    _require_platform_onboarding(actor)
    raise ValueError("Tenant merge requires a separately approved data-migration procedure")


def split_tenant(*, actor, **_kwargs) -> None:
    _require_platform_onboarding(actor)
    raise ValueError("Tenant split requires a separately approved data-migration procedure")
