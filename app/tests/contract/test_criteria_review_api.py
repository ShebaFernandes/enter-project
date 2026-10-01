from __future__ import annotations

import uuid

import pytest
from django.urls import reverse

from modules.audit.models import AuditEvent
from modules.operations.crypto import decrypt
from modules.operations.models import WorkflowRun


@pytest.mark.django_db
def test_ambiguous_prompt_routes_to_review_with_estimate(api_client, recruiter):
    api_client.force_login(recruiter.identity)
    response = api_client.post(
        reverse("search-interpret", kwargs={"tenant_id": recruiter.tenant_id}),
        {"prompt": "Maybe an engineer", "context": {"type": "AD_HOC"}},
        format="json",
        HTTP_X_TENANT_ID=str(recruiter.tenant_id),
    )

    assert response.status_code == 200
    assert response.data["requires_review"] is True
    assert isinstance(response.data["estimated_count"], int)
    assert response.data["original_prompt"] == "Maybe an engineer"
    event = AuditEvent.objects.get(action="SEARCH_CRITERIA_PREVIEW")
    assert "Maybe an engineer" not in str(event.metadata)
    assert event.metadata["ai_status"] == response.data["ai_status"]
    workflow = WorkflowRun.objects.get(pk=response.data["workflow_id"])
    assert workflow.status == WorkflowRun.Status.AWAITING_REVIEW
    assert "Maybe an engineer" not in decrypt(bytes(workflow.checkpoint_ciphertext))


@pytest.mark.django_db
def test_recruiter_edits_preserve_ids_and_override_interpretation(
    api_client, recruiter, search_payload
):
    api_client.force_login(recruiter.identity)
    interpreted = api_client.post(
        reverse("search-interpret", kwargs={"tenant_id": recruiter.tenant_id}),
        {"prompt": "Maybe Python engineer in Bengaluru", "context": {"type": "AD_HOC"}},
        format="json",
        HTTP_X_TENANT_ID=str(recruiter.tenant_id),
    )
    assert interpreted.data["requires_review"] is True
    assert WorkflowRun.objects.get(pk=interpreted.data["workflow_id"]).status == "AWAITING_REVIEW"
    criteria = interpreted.data["criteria"]
    original_group_id = criteria["groups"][0]["id"]
    original_criterion_id = criteria["criteria"][0]["id"]
    criteria["groups"][0]["operator"] = "ANY"
    criteria["criteria"][0]["value"] = "Django"

    reviewed = api_client.post(
        reverse("search-interpret", kwargs={"tenant_id": recruiter.tenant_id}),
        {
            "prompt": interpreted.data["original_prompt"],
            "context": criteria["context"],
            "criteria": criteria,
            "workflow_id": interpreted.data["workflow_id"],
        },
        format="json",
        HTTP_X_TENANT_ID=str(recruiter.tenant_id),
    )

    assert reviewed.status_code == 200
    assert reviewed.data["criteria"]["groups"][0]["id"] == original_group_id
    assert reviewed.data["criteria"]["criteria"][0]["id"] == original_criterion_id
    assert reviewed.data["criteria"]["criteria"][0]["value"] == "Django"
    assert reviewed.data["requires_review"] is False
    assert (
        WorkflowRun.objects.get(pk=interpreted.data["workflow_id"]).status
        == WorkflowRun.Status.COMPLETED
    )


@pytest.mark.django_db
@pytest.mark.parametrize("case", ["missing", "duplicate_group", "duplicate_criterion"])
def test_review_rejects_invalid_group_references(api_client, recruiter, search_payload, case):
    api_client.force_login(recruiter.identity)
    payload = {**search_payload}
    if case == "missing":
        payload["criteria"] = [{**payload["criteria"][0], "group_id": str(uuid.uuid4())}]
    elif case == "duplicate_group":
        payload["groups"] = [payload["groups"][0], payload["groups"][0]]
    else:
        payload["criteria"] = [payload["criteria"][0], payload["criteria"][0]]

    response = api_client.post(
        reverse("search-interpret", kwargs={"tenant_id": recruiter.tenant_id}),
        {
            "prompt": "Synthetic edited search",
            "context": payload["context"],
            "criteria": payload,
        },
        format="json",
        HTTP_X_TENANT_ID=str(recruiter.tenant_id),
    )
    assert response.status_code == 422


@pytest.mark.django_db
def test_cross_tenant_interpretation_is_denied(api_client, recruiter, tenant):
    other_tenant_id = uuid.uuid4()
    api_client.force_login(recruiter.identity)
    response = api_client.post(
        reverse("search-interpret", kwargs={"tenant_id": other_tenant_id}),
        {"prompt": "Python engineer", "context": {"type": "AD_HOC"}},
        format="json",
        HTTP_X_TENANT_ID=str(other_tenant_id),
    )
    assert response.status_code == 404
