import pytest
from django.core.cache import cache
from django.utils import timezone

from modules.identity.models import Identity
from modules.tenancy.models import Tenant, TenantMembership


@pytest.fixture(autouse=True)
def isolate_rate_limit_cache():
    cache.clear()
    yield
    cache.clear()


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


@pytest.fixture
def api_client():
    from rest_framework.test import APIClient

    return APIClient()


@pytest.fixture
def profile_factory(db):
    from modules.candidate.models import CandidateProfile
    from modules.identity.models import Identity, IdentityCapability
    from modules.operations.crypto import encrypt

    def factory(*, published=False):
        marker = __import__("uuid").uuid4().hex
        person = Identity.objects.create_user(
            cognito_subject=f"candidate-{marker}",
            email_lookup_hmac=f"hmac-{marker}".encode(),
            email_ciphertext=encrypt(f"candidate-{marker}@example.test"),
            email_verified_at=timezone.now(),
        )
        IdentityCapability.objects.create(identity=person, role="CANDIDATE", assigned_by=person)
        return CandidateProfile.objects.create(
            identity=person,
            full_name_ciphertext=encrypt("Synthetic Candidate"),
            location={"normalized": "bengaluru", "display": "Bengaluru"},
            experience_years=5,
            role_categories=["software engineer"],
            preferred_locations=["bengaluru"],
            work_arrangements=["REMOTE"],
            profile_state="PUBLISHED" if published else "DRAFT",
        )

    return factory


@pytest.fixture
def opening_factory(db, identity):
    from modules.recruiting.models import Opening
    from modules.tenancy.models import BusinessUnit

    def factory(*, tenant, state="OPEN"):
        unit = BusinessUnit.objects.create(
            tenant=tenant,
            name=f"Engineering-{__import__('uuid').uuid4().hex[:6]}",
            created_by=identity,
        )
        return Opening.objects.create(
            tenant=tenant,
            business_unit=unit,
            title="Software Engineer",
            location={"normalized": "bengaluru"},
            work_mode="REMOTE",
            employment_type="PERMANENT",
            state=state,
            created_by=identity,
        )

    return factory


@pytest.fixture
def search_payload():
    import uuid

    group_id = str(uuid.uuid4())
    return {
        "context": {"type": "AD_HOC"},
        "groups": [{"id": group_id, "purpose": "REQUIREMENT", "operator": "ANY", "label": "Core"}],
        "criteria": [
            {
                "id": str(uuid.uuid4()),
                "group_id": group_id,
                "field": "skill",
                "operator": "CONTAINS",
                "value": "Python",
            }
        ],
        "limit": 25,
    }


@pytest.fixture
def short_tenure_finding(profile_factory):
    from datetime import date

    from modules.candidate.finding_evaluators import evaluate_employment_record
    from modules.candidate.models import EmploymentRecord

    record = EmploymentRecord.objects.create(
        profile=profile_factory(),
        company="Synthetic Employer",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 9, 1),
        start_date_state="CONFIRMED",
        end_date_state="CONFIRMED",
        start_date_precision="DAY",
        end_date_precision="DAY",
        is_current=False,
        employment_type="PERMANENT",
        employment_type_state="CONFIRMED",
        provenance="CANDIDATE_REPORTED",
    )
    return evaluate_employment_record(record)
