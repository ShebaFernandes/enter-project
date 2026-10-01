import hashlib
from datetime import timedelta

import pytest
from django.utils import timezone

from modules.identity.models import SessionCredential

pytestmark = [pytest.mark.django_db, pytest.mark.postgres]


@pytest.fixture(autouse=True)
def enable_transport_for_security_tests(settings):
    settings.SEARCH_WORKFLOW_HANDOFF_ENABLED = True


def assured(client, identity):
    client.logout()
    client.force_login(identity)
    session = client.session
    credential = SessionCredential.objects.create(
        identity=identity,
        session_key_hash=hashlib.sha256(session.session_key.encode()).digest(),
        provider="TEST",
        assurance="WORKFORCE_MFA",
        authenticated_at=timezone.now(),
        expires_at=timezone.now() + timedelta(hours=1),
    )
    session["session_credential_id"] = str(credential.pk)
    session.save()
    return credential


@pytest.fixture
def handoff(api_client, recruiter, tenant):
    credential = assured(api_client, recruiter.identity)
    api_client.credentials(HTTP_X_TENANT_ID=str(tenant.pk))
    base = f"/api/v1/tenants/{tenant.pk}"
    interpreted = api_client.post(
        f"{base}/searches/interpret",
        {"prompt": "Maybe Python engineer", "context": {"type": "AD_HOC"}},
        format="json",
    ).json()
    # A review-only handoff must start from a genuinely ambiguous interpretation,
    # not a validated prompt that now correctly takes the direct-results path.
    assert interpreted["requires_review"] is True
    from modules.operations.models import WorkflowRun

    assert WorkflowRun.objects.get(pk=interpreted["workflow_id"]).status == "AWAITING_REVIEW"
    body = {"workflow_id": interpreted["workflow_id"], "criteria": interpreted["criteria"]}
    created = api_client.post(
        f"{base}/search-handoffs/criteria-review",
        body,
        format="json",
        HTTP_IDEMPOTENCY_KEY="synthetic-handoff-key-001",
    )
    assert created.status_code == 201
    return api_client, base, created.json(), credential, body


def test_bound_restore_no_store_and_no_prompt(handoff):
    client, base, created, _, _ = handoff
    response = client.get(
        f"{base}/search-handoffs/criteria-review", HTTP_X_WORKFLOW_HANDOFF=created["token"]
    )
    assert response.status_code == 200
    assert "no-store" in response["Cache-Control"]
    assert "criteria" in response.json()
    assert "original_prompt" not in response.json()
    assert "prompt" not in response.json()


def test_transport_is_unavailable_when_disabled(handoff, settings):
    client, base, created, _, _ = handoff
    settings.SEARCH_WORKFLOW_HANDOFF_ENABLED = False
    assert (
        client.get(
            f"{base}/search-handoffs/criteria-review", HTTP_X_WORKFLOW_HANDOFF=created["token"]
        ).status_code
        == 404
    )


@pytest.mark.parametrize(
    "change",
    [
        "expired",
        "revoked",
        "completed",
        "wrong_session",
        "wrong_kind",
        "unknown",
        "workflow_changed",
    ],
)
def test_invalid_handoffs_are_concealed(handoff, change):
    from modules.search.models import SearchWorkflowHandoff

    client, base, created, credential, _ = handoff
    item = SearchWorkflowHandoff.objects.get()
    kind = "criteria-review"
    token = created["token"]
    if change == "expired":
        item.expires_at = timezone.now() - timedelta(seconds=1)
    elif change in {"revoked", "completed"}:
        item.state = change.upper()
    elif change == "wrong_session":
        assured(client, credential.identity)
    elif change == "wrong_kind":
        kind = "search-results"
    elif change == "unknown":
        token = "x" * 43
    else:
        assert item.workflow is not None
        item.workflow.status = "COMPLETED"
        item.workflow.save()
    item.save()
    assert (
        client.get(f"{base}/search-handoffs/{kind}", HTTP_X_WORKFLOW_HANDOFF=token).status_code
        == 404
    )


def test_payload_encrypted_token_hash_only_and_retry_bounded(handoff):
    from modules.search.models import SearchWorkflowHandoff

    client, base, created, _, body = handoff
    item = SearchWorkflowHandoff.objects.get()
    assert item.token_hash == hashlib.sha256(created["token"].encode()).hexdigest()
    assert b"criteria" not in bytes(item.payload_ciphertext)
    replay = client.post(
        f"{base}/search-handoffs/criteria-review",
        body,
        format="json",
        HTTP_IDEMPOTENCY_KEY="synthetic-handoff-key-001",
    )
    assert replay.status_code == 200
    assert SearchWorkflowHandoff.objects.count() == 1
    assert (
        client.get(
            f"{base}/search-handoffs/criteria-review",
            HTTP_X_WORKFLOW_HANDOFF=replay.json()["token"],
        ).status_code
        == 200
    )


def test_revoked_session_cannot_restore(handoff):
    client, base, created, credential, _ = handoff
    credential.revoked_at = timezone.now()
    credential.save()
    assert client.get(
        f"{base}/search-handoffs/criteria-review", HTTP_X_WORKFLOW_HANDOFF=created["token"]
    ).status_code in {401, 403, 404}


def test_membership_loss_denies_restore(handoff, recruiter):
    client, base, created, _, _ = handoff
    recruiter.status = "REVOKED"
    recruiter.save()
    response = client.get(
        f"{base}/search-handoffs/criteria-review", HTTP_X_WORKFLOW_HANDOFF=created["token"]
    )
    assert response.status_code in {403, 404}


def test_rate_limit_and_malformed_token(handoff):
    client, base, _, _, _ = handoff
    for _ in range(61):
        response = client.get(
            f"{base}/search-handoffs/criteria-review", HTTP_X_WORKFLOW_HANDOFF="malformed"
        )
    assert response.status_code == 429
    assert "no-store" in response["Cache-Control"]


def test_results_restoration_is_metadata_only_and_closes_review(handoff):
    from modules.search.models import SearchDefinition

    client, base, created, _, body = handoff
    execution = client.post(f"{base}/searches", body["criteria"], format="json")
    assert execution.status_code == 200, execution.content
    response = client.post(
        f"{base}/search-handoffs/search-results",
        {"search_id": execution.json()["search_id"], "criteria_token": created["token"]},
        format="json",
        HTTP_IDEMPOTENCY_KEY="synthetic-results-key-001",
    )
    assert response.status_code == 201, response.content
    token = response.json()["token"]
    before = SearchDefinition.objects.count()
    for _ in range(2):
        restored = client.get(
            f"{base}/search-handoffs/search-results", HTTP_X_WORKFLOW_HANDOFF=token
        )
        assert restored.status_code == 200
        assert set(restored.json()) == {
            "schema_version",
            "version",
            "etag",
            "kind",
            "search_id",
            "result_context_version",
            "page",
            "criteria",
        }
        assert restored.json()["criteria"] == body["criteria"]
        assert "prompt" not in restored.json()
        assert "no-store" in restored["Cache-Control"]
    assert SearchDefinition.objects.count() == before
    for wrong_token in [created["token"], token]:
        assert (
            client.get(
                f"{base}/search-handoffs/criteria-review", HTTP_X_WORKFLOW_HANDOFF=wrong_token
            ).status_code
            == 404
        )


def test_criteria_identity_preserves_values_and_ids_but_ignores_retrieval_order(handoff):
    from copy import deepcopy

    from modules.search.handoffs import criteria_identity

    _, _, _, _, body = handoff
    original = deepcopy(body["criteria"])
    reordered = deepcopy(original)
    reordered["criteria"].reverse()
    reordered["groups"].reverse()
    assert criteria_identity(original) == criteria_identity(reordered)
    changed = deepcopy(original)
    changed["criteria"][0]["value"] = "Different requirement"
    assert criteria_identity(original) != criteria_identity(changed)


def test_revise_requires_etag_and_revoke_is_final(handoff):
    client, base, created, _, body = handoff
    url = f"{base}/search-handoffs/criteria-review"
    headers = {"HTTP_X_WORKFLOW_HANDOFF": created["token"]}
    restored = client.get(url, **headers).json()
    changed = client.patch(
        url,
        {"criteria": body["criteria"]},
        format="json",
        HTTP_IF_MATCH=restored["etag"],
        **headers,
    )
    assert changed.status_code == 200, changed.content
    stale = client.patch(
        url,
        {"criteria": body["criteria"]},
        format="json",
        HTTP_IF_MATCH=restored["etag"],
        **headers,
    )
    assert stale.status_code in {409, 412}
    assert client.delete(url, HTTP_IF_MATCH=changed.json()["etag"], **headers).status_code == 204
    assert client.get(url, **headers).status_code == 404


def test_creation_requires_csrf(handoff):
    from rest_framework.test import APIClient

    original, base, _, _, body = handoff
    client = APIClient(enforce_csrf_checks=True)
    client.cookies = original.cookies
    response = client.post(
        f"{base}/search-handoffs/criteria-review",
        body,
        format="json",
        HTTP_X_TENANT_ID=base.split("/")[-1],
        HTTP_IDEMPOTENCY_KEY="synthetic-csrf-key-001",
    )
    assert response.status_code == 403


def test_other_actor_and_tenant_denied(handoff, tenant):
    import uuid

    from modules.identity.models import Identity
    from modules.tenancy.models import Tenant, TenantMembership

    client, base, created, credential, _ = handoff
    person = Identity.objects.create_user(cognito_subject=f"other-{uuid.uuid4()}")
    TenantMembership.objects.create(
        tenant=tenant, identity=person, role="RECRUITER", status="ACTIVE"
    )
    assured(client, person)
    assert (
        client.get(
            f"{base}/search-handoffs/criteria-review", HTTP_X_WORKFLOW_HANDOFF=created["token"]
        ).status_code
        == 404
    )
    other = Tenant.objects.create(name="Other", slug="other-handoff", status="ACTIVE")
    TenantMembership.objects.create(
        tenant=other, identity=credential.identity, role="RECRUITER", status="ACTIVE"
    )
    assured(client, credential.identity)
    client.credentials(HTTP_X_TENANT_ID=str(other.pk))
    assert (
        client.get(
            f"/api/v1/tenants/{other.pk}/search-handoffs/criteria-review",
            HTTP_X_WORKFLOW_HANDOFF=created["token"],
        ).status_code
        == 404
    )


def test_handoff_audit_and_logs_exclude_token_payload(handoff, caplog):
    from modules.audit.models import AuditEvent

    client, base, created, _, _ = handoff
    client.get(f"{base}/search-handoffs/criteria-review", HTTP_X_WORKFLOW_HANDOFF=created["token"])
    events = list(AuditEvent.objects.filter(action__startswith="SEARCH_HANDOFF_").values())
    assert events
    material = str(events) + caplog.text
    assert created["token"] not in material
    assert "Python engineer" not in material
    assert "criteria" not in str([e["metadata"] for e in events]).replace("criteria-review", "")


def test_handoff_forced_rls_with_nonowner_role(handoff, tenant):
    import uuid

    from django.db import connection, transaction

    role = connection.ops.quote_name(f"handoff_reader_{uuid.uuid4().hex[:12]}")
    with connection.cursor() as cursor:
        cursor.execute(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
        cursor.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
        cursor.execute(f"GRANT SELECT ON search_searchworkflowhandoff TO {role}")
    try:
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(f"SET LOCAL ROLE {role}")
            cursor.execute("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname=current_user")
            assert cursor.fetchone() == (False, False)
            cursor.execute(
                "SELECT relforcerowsecurity, pg_get_userbyid(relowner) <> current_user "
                "FROM pg_class WHERE relname='search_searchworkflowhandoff'"
            )
            assert cursor.fetchone() == (True, True)
            cursor.execute("SELECT set_config('app.tenant_id', %s, true)", [str(tenant.pk)])
            cursor.execute("SELECT count(*) FROM search_searchworkflowhandoff")
            assert cursor.fetchone() == (1,)
            cursor.execute("SELECT set_config('app.tenant_id', %s, true)", [str(uuid.uuid4())])
            cursor.execute("SELECT count(*) FROM search_searchworkflowhandoff")
            assert cursor.fetchone() == (0,)
            cursor.execute("RESET ROLE")
    finally:
        with connection.cursor() as cursor:
            cursor.execute(f"DROP OWNED BY {role}")
            cursor.execute(f"DROP ROLE {role}")
