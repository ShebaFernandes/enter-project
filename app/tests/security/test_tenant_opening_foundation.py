import uuid
from dataclasses import replace
from typing import cast

import pytest
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.test import override_settings
from rest_framework.test import APIClient

from modules.identity.models import Identity, IdentityCapability
from modules.recruiting.models import Application, CandidateFacingStatus
from modules.recruiting.openings import create_opening, update_opening
from modules.recruiting.recruiter_entered import create_recruiter_entered_candidate
from modules.tenancy.models import BusinessUnit, TenantMembership
from modules.tenancy.policy import authorize_opening
from modules.tenancy.provisioning import provision_tenant
from tests.factories import IdentityFactory

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


def test_application_shell_has_unique_candidate_per_opening_and_eight_statuses(
    identity, recruiter, tenant
):
    unit = BusinessUnit.objects.create(tenant=tenant, name="Applications", created_by=identity)
    opening = create_opening(
        membership=recruiter,
        business_unit_id=unit.id,
        title="Foundation-only role",
        location={"country": "IN"},
        work_mode="REMOTE",
        employment_type="FULL_TIME",
    )
    candidate_profile_id = uuid.uuid4()
    Application.objects.create(
        tenant=tenant,
        opening=opening,
        candidate_profile_id=candidate_profile_id,
        suggested_candidate_status=None,
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        Application.objects.create(
            tenant=tenant,
            opening=opening,
            candidate_profile_id=candidate_profile_id,
        )
    assert {value for value, _ in CandidateFacingStatus.choices} == {
        "APPLIED",
        "PROFILE_VIEWED",
        "SHORTLISTED",
        "RECRUITER_INTERESTED",
        "INTERVIEW_REQUESTED",
        "OFFER_MADE",
        "NOT_SELECTED",
        "WITHDRAWN",
    }


def test_recruiter_entered_candidate_endpoint_is_tenant_scoped_and_immutable(recruiter, tenant):
    client = APIClient()
    client.force_login(recruiter.identity)
    path = f"/api/v1/tenants/{tenant.id}/recruiter-entered-candidates"
    response = client.post(
        path,
        {
            "display_name": "Synthetic Foundation Candidate",
            "location": {"city": "Pune", "country": "IN"},
            "experience_years": "3.25",
            "skills": ["Python"],
            "confirm_synthetic": True,
        },
        format="json",
        HTTP_X_TENANT_ID=str(tenant.id),
        HTTP_IDEMPOTENCY_KEY="synthetic-recruiter-candidate-1",
    )
    assert response.status_code == 201
    assert response.json()["source_type"] == "RECRUITER_ENTERED_SYNTHETIC"
    assert "email" not in response.json() and "resume" not in response.json()
    assert (
        client.get(path, HTTP_X_TENANT_ID=str(tenant.id)).json()[0]["id"] == response.json()["id"]
    )


def test_recruiter_entered_candidate_is_disabled_outside_synthetic_environments(recruiter, tenant):
    production_env = replace(settings.ENV, app_env="production")
    with override_settings(ENV=production_env), pytest.raises(PermissionDenied):
        create_recruiter_entered_candidate(
            membership=recruiter,
            actor=recruiter.identity,
            values={
                "display_name": "Synthetic only",
                "location": {"country": "IN"},
                "experience_years": 1,
                "skills": ["Testing"],
                "confirm_synthetic": True,
            },
        )


def test_hiring_manager_reads_only_assigned_openings(identity, recruiter, tenant):
    unit = BusinessUnit.objects.create(tenant=tenant, name="Scoped Unit", created_by=identity)
    opening = create_opening(
        membership=recruiter,
        business_unit_id=unit.id,
        title="Scoped Role",
        location={"country": "IN"},
        work_mode="HYBRID",
        employment_type="FULL_TIME",
    )
    manager = TenantMembership.objects.create(
        tenant=tenant,
        identity=cast(Identity, IdentityFactory()),
        role=TenantMembership.Role.HIRING_MANAGER,
        status=TenantMembership.Status.ACTIVE,
    )
    with pytest.raises(PermissionDenied):
        authorize_opening(manager, opening, "opening.read")
