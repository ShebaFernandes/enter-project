import pytest
from django.test import RequestFactory
from rest_framework.test import APIRequestFactory

from modules.abuse.service import check
from modules.operations.concurrency import StaleWrite, require_match, strong_etag
from modules.operations.idempotency import complete, reserve
from modules.operations.problems import problem_exception_handler

pytestmark = pytest.mark.django_db


def test_strong_etag_rejects_stale_write_with_reconciliation_payload():
    with pytest.raises(StaleWrite) as caught:
        require_match(
            '"stale"',
            object_id="object-1",
            version=2,
            current={"status": "OPEN"},
            attempted={"status": "CLOSED"},
        )
    assert caught.value.detail["changed_fields"] == ["status"]
    assert caught.value.detail["current_etag"] == strong_etag("object-1", 2)


def test_problem_response_is_rfc9457_shaped():
    request = APIRequestFactory().get("/")
    request.correlation_id = "request-1"
    response = problem_exception_handler(
        StaleWrite(current={"x": 1}, attempted={"x": 2}, object_id="1", version=1),
        {"request": request},
    )
    assert response.status_code == 409
    assert response.data["request_id"] == "request-1"
    assert response.data["current"] == {"x": 1}


def test_idempotency_replays_completed_response():
    record, created = reserve("actor", "key", {"name": "synthetic"})
    assert created
    complete(record, 201, {"id": "synthetic-id"})
    replay, created = reserve("actor", "key", {"name": "synthetic"})
    assert not created
    assert replay.response_status == 201


def test_rate_limit_combines_identity_and_network():
    request = RequestFactory(REMOTE_ADDR="203.0.113.5").post("/api/v1/auth/login")
    request.user = type("Anonymous", (), {"is_authenticated": False})()
    allowed, remaining, retry = check(request, "sign-in")
    assert allowed and remaining >= 0 and retry == 0
