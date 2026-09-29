import factory

from modules.identity.models import Identity, IdentityCapability
from modules.recruiting.models import Opening
from modules.tenancy.models import BusinessUnit, Tenant, TenantMembership


class IdentityFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Identity

    cognito_subject = factory.Sequence(lambda n: f"synthetic-subject-{n}")
    email_lookup_hmac = factory.Sequence(lambda n: f"hmac-{n}".encode())
    email_ciphertext = factory.Sequence(lambda n: f"cipher-{n}".encode())


class TenantFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Tenant

    name = factory.Sequence(lambda n: f"Synthetic Company {n}")
    slug = factory.Sequence(lambda n: f"synthetic-company-{n}")
    legal_boundary_reference = factory.Sequence(lambda n: f"contract-{n}")
    status = Tenant.Status.ACTIVE


class MembershipFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = TenantMembership

    tenant = factory.SubFactory(TenantFactory)
    identity = factory.SubFactory(IdentityFactory)
    role = TenantMembership.Role.RECRUITER
    status = TenantMembership.Status.ACTIVE


class BusinessUnitFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = BusinessUnit

    tenant = factory.SubFactory(TenantFactory)
    name = factory.Sequence(lambda n: f"Synthetic Unit {n}")
    created_by = factory.SubFactory(IdentityFactory)


class OpeningFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Opening

    tenant = factory.SelfAttribute("business_unit.tenant")
    business_unit = factory.SubFactory(BusinessUnitFactory)
    title = factory.Sequence(lambda n: f"Synthetic Role {n}")
    location = {"city": "Bengaluru", "country": "IN"}
    work_mode = Opening.WorkMode.HYBRID
    employment_type = "FULL_TIME"
    created_by = factory.SubFactory(IdentityFactory)


class CandidateCapabilityFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = IdentityCapability

    identity = factory.SubFactory(IdentityFactory)
    role = IdentityCapability.Role.CANDIDATE
    assigned_by = factory.SubFactory(IdentityFactory)
