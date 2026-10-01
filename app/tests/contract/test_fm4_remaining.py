import pytest

from tests.security.test_search_handoffs import assured

pytestmark = [pytest.mark.django_db, pytest.mark.postgres]


@pytest.mark.parametrize("loss", ["closed", "scope"])
def test_restore_rechecks_opening_authorization(api_client, recruiter, opening_factory, loss):
    import uuid

    opening = opening_factory(tenant=recruiter.tenant)
    assured(api_client, recruiter.identity)
    api_client.credentials(HTTP_X_TENANT_ID=str(recruiter.tenant_id))
    base = f"/api/v1/tenants/{recruiter.tenant_id}"
    interpreted = api_client.post(
        base + "/searches/interpret",
        {"prompt": "Python", "context": {"type": "OPENING", "opening_id": str(opening.pk)}},
        format="json",
    ).json()
    created = api_client.post(
        base + "/search-handoffs/criteria-review",
        {"workflow_id": interpreted["workflow_id"], "criteria": interpreted["criteria"]},
        format="json",
        HTTP_IDEMPOTENCY_KEY="opening-restore-test-001",
    )
    assert created.status_code == 201
    if loss == "closed":
        opening.state = "CLOSED"
        opening.save()
    else:
        recruiter.scope = {"opening_ids": [str(uuid.uuid4())]}
        recruiter.save()
    assert (
        api_client.get(
            base + "/search-handoffs/criteria-review",
            HTTP_X_WORKFLOW_HANDOFF=created.json()["token"],
        ).status_code
        == 404
    )


def test_recent_projection_keeps_active_source_and_conceals_other_owner(
    api_client, recruiter, search_payload
):
    from modules.identity.models import Identity
    from modules.search.models import SearchDefinition
    from modules.tenancy.models import TenantMembership

    assured(api_client, recruiter.identity)
    api_client.credentials(HTTP_X_TENANT_ID=str(recruiter.tenant_id))
    base = f"/api/v1/tenants/{recruiter.tenant_id}"
    source = api_client.post(base + "/searches", search_payload, format="json").json()["search_id"]
    token = api_client.post(
        base + "/search-handoffs/search-results",
        {"search_id": source},
        format="json",
        HTTP_IDEMPOTENCY_KEY="retained-source-test-001",
    ).json()["token"]
    for _ in range(7):
        assert api_client.post(base + "/searches", search_payload, format="json").status_code == 200
    assert SearchDefinition.objects.filter(pk=source).exists()
    assert len(api_client.get(base + "/recent-searches").json()) == 6
    assert (
        api_client.get(
            base + "/search-handoffs/search-results", HTTP_X_WORKFLOW_HANDOFF=token
        ).status_code
        == 200
    )
    actor = Identity.objects.create_user(cognito_subject="other-recent-owner")
    TenantMembership.objects.create(
        tenant=recruiter.tenant, identity=actor, role="RECRUITER", status="ACTIVE"
    )
    assured(api_client, actor)
    api_client.credentials(HTTP_X_TENANT_ID=str(recruiter.tenant_id))
    assert api_client.get(base + "/recent-searches").json() == []
    assert api_client.get(base + "/recent-searches/" + source).status_code == 404
    assert (
        api_client.post(
            base + "/search-handoffs/criteria-review",
            {"search_id": source},
            format="json",
            HTTP_IDEMPOTENCY_KEY="other-reopen-test-001",
        ).status_code
        == 404
    )


def test_recent_reopens_into_bound_review(api_client, recruiter, search_payload):
    assured(api_client, recruiter.identity)
    headers = {"HTTP_X_TENANT_ID": str(recruiter.tenant_id)}
    base = f"/api/v1/tenants/{recruiter.tenant_id}"
    for _ in range(7):
        result = api_client.post(base + "/searches", search_payload, format="json", **headers)
        assert result.status_code == 200
    recents = api_client.get(base + "/recent-searches", **headers)
    assert recents.status_code == 200
    assert len(recents.json()) == 6
    source = recents.json()[0]["search_id"]
    created = api_client.post(
        base + "/search-handoffs/criteria-review",
        {"search_id": source},
        format="json",
        HTTP_IDEMPOTENCY_KEY="fm4-reopen-retry-0001",
        **headers,
    )
    assert created.status_code == 201
    restored = api_client.get(
        base + "/search-handoffs/criteria-review",
        HTTP_X_WORKFLOW_HANDOFF=created.json()["token"],
        **headers,
    )
    assert restored.status_code == 200
    assert restored.json()["criteria"] == search_payload


def test_search_home_renderer_and_results_legacy(client, recruiter, settings):
    client.force_login(recruiter.identity)
    route = f"/tenants/{recruiter.tenant_id}/recruiter/search/"
    settings.FRONTEND_REACT_ROUTES = {"recruiter-search-page": True}
    home = client.get(route).content.decode()
    assert 'data-frontend-renderer="react"' in home
    assert "data-recruiter-search" not in home
    results = client.get(route + "?view=results").content.decode()
    assert 'data-frontend-renderer="legacy"' in results
    settings.FRONTEND_REACT_ROUTES = {}
    assert 'data-frontend-renderer="legacy"' in client.get(route).content.decode()


def test_pagination_persists_order_and_restores_without_new_search(
    api_client, recruiter, profile_factory, search_payload
):
    from modules.search.models import SearchDefinition
    from tests.contract.test_comparison_api import comparison_profile

    for index in range(5):
        comparison_profile(
            profile_factory=profile_factory, recruiter=recruiter, name_suffix=str(index)
        )
    assured(api_client, recruiter.identity)
    api_client.credentials(HTTP_X_TENANT_ID=str(recruiter.tenant_id))
    base = f"/api/v1/tenants/{recruiter.tenant_id}"
    search_payload["criteria"][0].update(field="experience_years", operator="GTE", value=0)
    search_payload["limit"] = 2
    run = api_client.post(base + "/searches", search_payload, format="json").json()
    assert len(run["items"]) == 2
    assert SearchDefinition.objects.get(pk=run["search_id"]).results.count() == 5
    first = api_client.post(
        base + "/search-handoffs/search-results",
        {"search_id": run["search_id"]},
        format="json",
        HTTP_IDEMPOTENCY_KEY="fm4-page-first-001",
    ).json()["token"]
    current = first
    for page_number, count in [(1, 2), (2, 4), (3, 5)]:
        for _ in range(2):
            display = api_client.get(
                base + "/search-handoffs/search-results/display", HTTP_X_WORKFLOW_HANDOFF=current
            )
            assert display.status_code == 200
            assert len(display.json()["items"]) == count
            ids = [item["candidate_id"] for item in display.json()["items"]]
            assert ids == sorted(ids)
        next_result = api_client.post(
            base + "/search-handoffs/search-results/page",
            {},
            format="json",
            HTTP_X_WORKFLOW_HANDOFF=current,
            HTTP_IDEMPOTENCY_KEY=f"fm4-next-page-{page_number}-001",
        )
        if page_number < 3:
            assert next_result.status_code == 201
            current = next_result.json()["token"]
        else:
            assert next_result.status_code == 422
    assert SearchDefinition.objects.count() == 1
    selection = api_client.post(
        base + "/search-handoffs/comparison-selection",
        {"search_id": run["search_id"], "candidate_ids": [ids[-1]]},
        format="json",
        HTTP_IDEMPOTENCY_KEY="fm4-final-page-selection",
    )
    assert selection.status_code == 201
    returned = api_client.post(
        base + "/search-handoffs/comparison-selection/return",
        {},
        format="json",
        HTTP_X_WORKFLOW_HANDOFF=selection.json()["token"],
        HTTP_IDEMPOTENCY_KEY="fm4-final-page-return",
    )
    assert returned.status_code == 200
    returned_token = returned.json()["return_path"].split("#handoff=")[1].split("&")[0]
    assert (
        api_client.get(
            base + "/search-handoffs/search-results", HTTP_X_WORKFLOW_HANDOFF=returned_token
        ).json()["page"]
        == 3
    )
    assert (
        len(
            api_client.get(
                base + "/search-handoffs/search-results/display", HTTP_X_WORKFLOW_HANDOFF=first
            ).json()["items"]
        )
        == 2
    )
