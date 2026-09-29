import pytest
from django.core.exceptions import PermissionDenied, ValidationError

from modules.identity.models import IdentityCapability
from modules.recruiting.openings import create_opening, update_opening
from modules.tenancy.models import BusinessUnit, TenantMembership
from modules.tenancy.provisioning import provision_tenant

pytestmark = pytest.mark.django_db


def test_opening_cannot_cross_business_unit_tenant(identity, recruiter):
    IdentityCapability.objects.create(
        identity=identity,
        role=IdentityCapability.Role.PLATFORM_SECURITY_ADMIN,
        assigned_by=identity,
    )
    other = provision_tenant(
        actor=identity,
        contracted_company_name="Other Synthetic",
        legal_boundary_reference="other-contract",
    )
    unit = BusinessUnit.objects.create(tenant=other, name="Other Unit", created_by=identity)
    with pytest.raises(BusinessUnit.DoesNotExist):
        create_opening(
            membership=recruiter,
            business_unit_id=unit.id,
            title="Role",
            location={},
            work_mode="REMOTE",
            employment_type="FULL_TIME",
        )


def test_hiring_manager_cannot_create_opening(identity, tenant):
    membership = TenantMembership.objects.create(
        tenant=tenant,
        identity=identity,
        role=TenantMembership.Role.HIRING_MANAGER,
        status=TenantMembership.Status.ACTIVE,
    )
    unit = BusinessUnit.objects.create(tenant=tenant, name="Unit", created_by=identity)
    with pytest.raises(PermissionDenied):
        create_opening(
            membership=membership,
            business_unit_id=unit.id,
            title="Role",
            location={},
            work_mode="REMOTE",
            employment_type="FULL_TIME",
        )


def test_recruiter_object_scope_and_opening_transitions_are_enforced(identity, recruiter, tenant):
    allowed = BusinessUnit.objects.create(tenant=tenant, name="Allowed", created_by=identity)
    denied = BusinessUnit.objects.create(tenant=tenant, name="Denied", created_by=identity)
    recruiter.scope = {"business_unit_ids": [str(allowed.id)]}
    recruiter.save(update_fields=("scope",))
    with pytest.raises(ValidationError):
        create_opening(
            membership=recruiter,
            business_unit_id=denied.id,
            title="Denied Role",
            location={},
            work_mode="REMOTE",
            employment_type="FULL_TIME",
        )
    opening = create_opening(
        membership=recruiter,
        business_unit_id=allowed.id,
        title="Allowed Role",
        location={"city": "Bengaluru", "country": "IN"},
        work_mode="REMOTE",
        employment_type="FULL_TIME",
    )
    update_opening(
        opening=opening,
        membership=recruiter,
        changes={"state": "CLOSED"},
    )
    with pytest.raises(ValidationError):
        update_opening(
            opening=opening,
            membership=recruiter,
            changes={"state": "OPEN"},
        )
