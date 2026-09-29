from django.db import transaction

from .models import BusinessUnit, TenantMembership
from .policy import AuthorizationRequest, authorize


@transaction.atomic
def create_business_unit(
    *, membership: TenantMembership, name: str, description: str = ""
) -> BusinessUnit:
    authorize(
        AuthorizationRequest(
            action="business_unit.write",
            role=membership.role,
            tenant_id=membership.tenant_id,
            object_tenant_id=membership.tenant_id,
        )
    )
    if membership.tenant.status != "ACTIVE":
        raise ValueError("Tenant must be active")
    unit = BusinessUnit(
        tenant=membership.tenant,
        created_by=membership.identity,
        name=name.strip(),
        description=description,
    )
    unit.full_clean()
    unit.save()
    return unit


@transaction.atomic
def update_business_unit(
    *, unit: BusinessUnit, membership: TenantMembership, changes: dict
) -> BusinessUnit:
    authorize(
        AuthorizationRequest(
            action="business_unit.write",
            role=membership.role,
            tenant_id=membership.tenant_id,
            object_tenant_id=unit.tenant_id,
        )
    )
    for key in {"name", "description", "status"} & changes.keys():
        setattr(unit, key, changes[key])
    unit.version += 1
    unit.full_clean()
    unit.save()
    return unit
