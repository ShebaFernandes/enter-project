from django.core.management.base import BaseCommand

from modules.identity.models import Identity, IdentityCapability
from modules.recruiting.openings import create_opening
from modules.tenancy.business_units import create_business_unit
from modules.tenancy.models import Tenant, TenantMembership


class Command(BaseCommand):
    help = "Load deterministic synthetic-only identities, roles, tenant, unit, and opening."

    def handle(self, *args, **options):
        tenant, _ = Tenant.objects.get_or_create(
            slug="synthetic-company",
            defaults={
                "name": "Synthetic Company",
                "legal_boundary_reference": "synthetic-contract",
                "status": Tenant.Status.ACTIVE,
            },
        )
        identities = {}
        for role in ("candidate", "recruiter", "hiring-manager", "tenant-admin", "security-admin"):
            identity, _ = Identity.objects.get_or_create(
                cognito_subject=f"synthetic-{role}",
                defaults={
                    "email_lookup_hmac": f"synthetic-hmac-{role}".encode(),
                    "email_ciphertext": f"synthetic-cipher-{role}".encode(),
                },
            )
            identities[role] = identity
        for role, membership_role in (
            ("recruiter", TenantMembership.Role.RECRUITER),
            ("hiring-manager", TenantMembership.Role.HIRING_MANAGER),
            ("tenant-admin", TenantMembership.Role.TENANT_ADMIN),
        ):
            TenantMembership.objects.get_or_create(
                tenant=tenant,
                identity=identities[role],
                defaults={"role": membership_role, "status": TenantMembership.Status.ACTIVE},
            )
        for role, capability in (
            ("candidate", IdentityCapability.Role.CANDIDATE),
            ("security-admin", IdentityCapability.Role.PLATFORM_SECURITY_ADMIN),
        ):
            IdentityCapability.objects.get_or_create(
                identity=identities[role],
                role=capability,
                defaults={"assigned_by": identities["security-admin"]},
            )
        recruiter = TenantMembership.objects.get(tenant=tenant, identity=identities["recruiter"])
        unit = tenant.business_units.filter(name="Synthetic Engineering").first()
        if unit is None:
            unit = create_business_unit(membership=recruiter, name="Synthetic Engineering")
        if not tenant.openings.filter(title="Synthetic Backend Engineer").exists():
            create_opening(
                membership=recruiter,
                business_unit_id=unit.id,
                title="Synthetic Backend Engineer",
                location={"city": "Bengaluru", "country": "IN"},
                work_mode="HYBRID",
                employment_type="FULL_TIME",
            )
        self.stdout.write(self.style.SUCCESS("Synthetic foundation loaded"))
