import uuid

import pytest
from django.core.exceptions import ValidationError

from modules.operations.concurrency import strong_etag
from modules.recruiting.models import RecruiterEnteredCandidate
from modules.search.models import CriteriaGroup, Criterion, SearchDefinition
from modules.tenancy.models import BusinessUnit
from tests.factories import ApplicationFactory, MembershipFactory, TenantFactory

pytestmark = pytest.mark.django_db


def tenant_request(client, membership, method, path, data=None, **headers):
    client.force_login(membership.identity)
    return getattr(client, method)(
        path,
        data or {},
        format="json",
        HTTP_X_TENANT_ID=str(membership.tenant_id),
        **headers,
    )


def opening_search(*, recruiter, opening):
    search = SearchDefinition.objects.create(
        tenant=recruiter.tenant,
        actor=recruiter.identity,
        prompt="Synthetic platform engineer",
        context_type="OPENING",
        criteria_context={"type": "OPENING", "opening_id": str(opening.id)},
        derived_opening=opening,
    )
    group = CriteriaGroup.objects.create(
        search=search,
        stable_id=uuid.uuid4(),
        purpose="REQUIREMENT",
        operator="ALL",
        label="Skills",
    )
    Criterion.objects.create(
        search=search,
        group=group,
        stable_id=uuid.uuid4(),
        field="skill",
        operator="CONTAINS",
        value="Python",
    )
    return search


def test_organization_lifecycle_synthetic_provenance_and_stale_conflicts(
    api_client, recruiter, tenant_admin
):
    tenant_id = recruiter.tenant_id
    units_path = f"/api/v1/tenants/{tenant_id}/business-units"
    created_unit = tenant_request(
        api_client,
        tenant_admin,
        "post",
        units_path,
        {"name": "Synthetic Engineering", "description": "Synthetic only"},
        HTTP_IDEMPOTENCY_KEY="phase9-org-unit-0001",
    )
    assert created_unit.status_code == 201, created_unit.data
    unit = created_unit.json()

    openings_path = f"/api/v1/tenants/{tenant_id}/openings"
    created_opening = tenant_request(
        api_client,
        tenant_admin,
        "post",
        openings_path,
        {
            "business_unit_id": unit["id"],
            "title": "Synthetic Platform Engineer",
            "location": {"display": "Bengaluru"},
            "work_mode": "HYBRID",
            "employment_type": "PERMANENT",
            "description": "Synthetic opening",
        },
        HTTP_IDEMPOTENCY_KEY="phase9-org-opening-0001",
    )
    assert created_opening.status_code == 201, created_opening.data
    opening = created_opening.json()

    synthetic = tenant_request(
        api_client,
        recruiter,
        "post",
        f"/api/v1/tenants/{tenant_id}/recruiter-entered-candidates",
        {
            "display_name": "Synthetic Phase Nine Candidate",
            "location": {"display": "Pune"},
            "experience_years": "4.25",
            "skills": ["Python"],
            "confirm_synthetic": True,
        },
        HTTP_IDEMPOTENCY_KEY="phase9-org-synthetic-0001",
    )
    assert synthetic.status_code == 201, synthetic.data
    assert synthetic.json()["source_type"] == "RECRUITER_ENTERED_SYNTHETIC"
    assert synthetic.json()["source_label"] == "Recruiter-entered synthetic record"
    assert not ({"email", "phone", "resume"} & set(synthetic.json()))

    unit_model = BusinessUnit.objects.get(pk=unit["id"])
    stale = tenant_request(
        api_client,
        tenant_admin,
        "patch",
        f"{units_path}/{unit['id']}",
        {"description": "Stale overwrite"},
        HTTP_IF_MATCH=strong_etag(unit_model.id, unit_model.version + 1),
        HTTP_IDEMPOTENCY_KEY="phase9-org-unit-stale",
    )
    assert stale.status_code == 409
    assert stale.json()["current"]["description"] == "Synthetic only"
    assert stale.json()["attempted"]["description"] == "Stale overwrite"

    candidate = RecruiterEnteredCandidate.objects.get(pk=synthetic.json()["id"])
    candidate.source_label = "Candidate submitted"
    with pytest.raises(ValidationError):
        candidate.full_clean()

    other = MembershipFactory(tenant=TenantFactory(), recruiter=True)
    denied = tenant_request(
        api_client,
        other,
        "get",
        f"/api/v1/tenants/{other.tenant_id}/openings/{opening['id']}",
    )
    assert denied.status_code == 404


def test_tenant_admin_can_edit_and_delete_an_empty_draft(api_client, tenant_admin, opening_factory):
    opening = opening_factory(tenant=tenant_admin.tenant, state="DRAFT")
    path = f"/api/v1/tenants/{tenant_admin.tenant_id}/openings/{opening.id}"

    updated = tenant_request(
        api_client,
        tenant_admin,
        "patch",
        path,
        {
            "title": "Applied AI Engineer",
            "location": {"display": "Mumbai"},
            "work_mode": "HYBRID",
            "employment_type": "CONTRACT",
            "description": "Build and evaluate recruiting models.",
        },
        HTTP_IF_MATCH=strong_etag(opening.id, opening.version),
        HTTP_IDEMPOTENCY_KEY="opening-edit-contract",
    )

    assert updated.status_code == 200, updated.data
    assert updated.json()["title"] == "Applied AI Engineer"
    assert updated.json()["location"] == {"display": "Mumbai"}
    assert updated.json()["work_mode"] == "HYBRID"
    assert updated.json()["employment_type"] == "CONTRACT"

    deleted = tenant_request(
        api_client,
        tenant_admin,
        "delete",
        path,
        HTTP_IF_MATCH=updated["ETag"],
        HTTP_IDEMPOTENCY_KEY="opening-delete-contract",
    )
    assert deleted.status_code == 204, deleted.data


def test_job_with_applicants_cannot_be_deleted(api_client, tenant_admin, opening_factory):
    opening = opening_factory(tenant=tenant_admin.tenant, state="DRAFT")
    ApplicationFactory(opening=opening)
    path = f"/api/v1/tenants/{tenant_admin.tenant_id}/openings/{opening.id}"

    response = tenant_request(
        api_client,
        tenant_admin,
        "delete",
        path,
        HTTP_IF_MATCH=strong_etag(opening.id, opening.version),
        HTTP_IDEMPOTENCY_KEY="opening-delete-blocked-contract",
    )

    assert response.status_code == 422, response.data
    assert "closed instead of deleted" in str(response.json())


def test_saved_search_has_only_authoritative_context_and_detects_changes(
    api_client, recruiter, opening_factory
):
    opening = opening_factory(tenant=recruiter.tenant)
    search = opening_search(recruiter=recruiter, opening=opening)
    path = f"/api/v1/tenants/{recruiter.tenant_id}/saved-searches"

    rejected = tenant_request(
        api_client,
        recruiter,
        "post",
        path,
        {
            "name": "Synthetic opening search",
            "search_id": str(search.id),
            "opening_id": str(opening.id),
        },
        HTTP_IDEMPOTENCY_KEY="phase9-saved-invalid-opening",
    )
    assert rejected.status_code == 422

    created = tenant_request(
        api_client,
        recruiter,
        "post",
        path,
        {"name": "Synthetic opening search", "search_id": str(search.id)},
        HTTP_IDEMPOTENCY_KEY="phase9-saved-opening-0001",
    )
    assert created.status_code == 201, created.data
    body = created.json()
    assert "opening_id" not in body
    assert body["criteria"]["context"] == {
        "type": "OPENING",
        "opening_id": str(opening.id),
    }
    assert body["changed_since_save"] == []

    opening.state = "PAUSED"
    opening.version += 1
    opening.save(update_fields=("state", "version"))
    reopened = tenant_request(
        api_client,
        recruiter,
        "get",
        f"{path}/{search.id}",
    )
    assert reopened.status_code == 200
    assert reopened.json()["changed_since_save"] == ["OPENING_STATE"]
    assert "opening_id" not in reopened.json()


def test_tenant_admin_metadata_does_not_gain_candidate_content(api_client, tenant):
    admin = MembershipFactory(tenant=tenant, tenant_admin=True)
    path = f"/api/v1/tenants/{tenant.id}/recruiter-entered-candidates"
    response = tenant_request(api_client, admin, "get", path)
    assert response.status_code in {403, 404}
