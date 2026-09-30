import uuid

import pytest
from django.urls import reverse

from modules.search.models import SearchDefinition


@pytest.mark.django_db
def test_execute_search_rejects_independent_opening(api_client, recruiter):
    api_client.force_login(recruiter.identity)
    response = api_client.post(
        reverse("search-list", kwargs={"tenant_id": recruiter.tenant_id}),
        {
            "context": {"type": "AD_HOC"},
            "opening_id": str(uuid.uuid4()),
            "groups": [],
            "criteria": [],
        },
        format="json",
        HTTP_X_TENANT_ID=str(recruiter.tenant_id),
    )
    assert response.status_code == 422


@pytest.mark.django_db
def test_execute_search_returns_cursor_shape(api_client, recruiter, search_payload):
    api_client.force_login(recruiter.identity)
    response = api_client.post(
        reverse("search-list", kwargs={"tenant_id": recruiter.tenant_id}),
        search_payload,
        format="json",
        HTTP_X_TENANT_ID=str(recruiter.tenant_id),
    )
    assert response.status_code == 200
    assert set(response.data) == {"items", "next_cursor", "search_id"}


@pytest.mark.django_db
def test_context_shapes_group_references_and_cursor_errors(api_client, recruiter, search_payload):
    api_client.force_login(recruiter.identity)
    headers = {"HTTP_X_TENANT_ID": str(recruiter.tenant_id)}
    payload = {**search_payload, "context": {"type": "AD_HOC", "opening_id": str(uuid.uuid4())}}
    assert (
        api_client.post(
            reverse("search-list", kwargs={"tenant_id": recruiter.tenant_id}),
            payload,
            format="json",
            **headers,
        ).status_code
        == 422
    )
    payload = {**search_payload, "context": {"type": "OPENING"}}
    assert (
        api_client.post(
            reverse("search-list", kwargs={"tenant_id": recruiter.tenant_id}),
            payload,
            format="json",
            **headers,
        ).status_code
        == 422
    )
    payload = {**search_payload, "cursor": "not-base64"}
    assert (
        api_client.post(
            reverse("search-list", kwargs={"tenant_id": recruiter.tenant_id}),
            payload,
            format="json",
            **headers,
        ).status_code
        == 422
    )


@pytest.mark.django_db
def test_recent_search_cap_and_saved_search_round_trip(api_client, recruiter, search_payload):
    api_client.force_login(recruiter.identity)
    url = reverse("search-list", kwargs={"tenant_id": recruiter.tenant_id})
    headers = {"HTTP_X_TENANT_ID": str(recruiter.tenant_id)}
    search_id = None
    for _ in range(7):
        payload = {**search_payload}
        group_id = str(uuid.uuid4())
        payload["groups"] = [
            {"id": group_id, "purpose": "REQUIREMENT", "operator": "ANY", "label": "Core"}
        ]
        payload["criteria"] = [
            {
                "id": str(uuid.uuid4()),
                "group_id": group_id,
                "field": "skill",
                "operator": "CONTAINS",
                "value": "Python",
            }
        ]
        response = api_client.post(url, payload, format="json", **headers)
        assert response.status_code == 200
        search_id = response.data["search_id"]
    assert (
        SearchDefinition.objects.filter(
            tenant_id=recruiter.tenant_id, actor=recruiter.identity
        ).count()
        == 6
    )

    saved_url = reverse("saved-search-list", kwargs={"tenant_id": recruiter.tenant_id})
    saved = api_client.post(
        saved_url,
        {"name": "Synthetic saved search", "search_id": search_id},
        format="json",
        **headers,
    )
    assert saved.status_code == 201
    assert "opening_id" not in saved.data
    assert saved.data["criteria"]["context"] == {"type": "AD_HOC"}
    assert api_client.get(saved_url, **headers).data[0]["search_id"] == search_id
    reopened = api_client.get(
        reverse(
            "saved-search-detail",
            kwargs={"tenant_id": recruiter.tenant_id, "search_id": search_id},
        ),
        **headers,
    )
    assert reopened.status_code == 200
    assert reopened.data["criteria"]["groups"][0]["id"]
