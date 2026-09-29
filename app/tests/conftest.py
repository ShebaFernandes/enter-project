import pytest

from modules.identity.models import Identity
from modules.tenancy.models import Tenant, TenantMembership


@pytest.fixture
def identity(db):
    return Identity.objects.create_user(
        cognito_subject="fixture-subject",
        email_lookup_hmac=b"fixture-hmac",
        email_ciphertext=b"fixture-ciphertext",
    )


@pytest.fixture
def tenant(db):
    return Tenant.objects.create(
        name="Synthetic Company",
        slug="synthetic-company",
        legal_boundary_reference="contract-synthetic",
        status=Tenant.Status.ACTIVE,
    )


@pytest.fixture
def recruiter(identity, tenant):
    return TenantMembership.objects.create(
        tenant=tenant,
        identity=identity,
        role=TenantMembership.Role.RECRUITER,
        status=TenantMembership.Status.ACTIVE,
    )
