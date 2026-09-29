from datetime import timedelta

import pytest
from django.core.cache import cache
from django.test import RequestFactory
from django.utils import timezone

from modules.abuse.policy import LIMITS, create_override, escalation_delay, tightened
from modules.abuse.service import check, signal_token
from modules.audit.models import AuditEvent

pytestmark = pytest.mark.django_db


def test_every_sensitive_action_has_a_balanced_limit():
    assert set(LIMITS) == {"sign-in", "otp", "upload", "application", "search", "export"}
    assert all(item.attempts > 0 and item.window_seconds > 0 for item in LIMITS.values())


def test_delay_escalates_but_never_permanently_locks():
    assert escalation_delay(3) > escalation_delay(1)
    assert escalation_delay(100) <= 900


def test_anomaly_tightening_reduces_allowance():
    assert tightened(LIMITS["search"], 2).attempts < LIMITS["search"].attempts


@pytest.mark.parametrize("action", sorted(LIMITS))
def test_every_action_threshold_returns_retry_after(action):
    address_suffix = list(sorted(LIMITS)).index(action) + 7
    request = RequestFactory(REMOTE_ADDR=f"198.51.100.{address_suffix}").post(f"/api/v1/{action}")
    request.user = type("Anonymous", (), {"is_authenticated": False})()
    results = [check(request, action) for _ in range(LIMITS[action].attempts + 1)]
    assert results[-1][0] is False
    assert results[-1][2] > 0


def test_identity_and_network_signals_are_both_part_of_the_bucket(identity):
    factory = RequestFactory()
    first = factory.post("/api/v1/otp", REMOTE_ADDR="198.51.100.10")
    first.user = identity
    second_network = factory.post("/api/v1/otp", REMOTE_ADDR="198.51.100.11")
    second_network.user = identity
    anonymous = factory.post("/api/v1/otp", REMOTE_ADDR="198.51.100.10")
    anonymous.user = type("Anonymous", (), {"is_authenticated": False})()
    assert signal_token(first) != signal_token(second_network)
    assert signal_token(first) != signal_token(anonymous)


def test_authorized_override_is_temporary_and_audited(identity):
    request = RequestFactory(REMOTE_ADDR="203.0.113.7").post("/api/v1/otp")
    request.user = identity
    token = signal_token(request)
    create_override(
        subject_token=token,
        action="otp",
        reason_code="VERIFIED_SUPPORT_RECOVERY",
        approved_by=identity,
        expires_at=timezone.now() + timedelta(minutes=5),
    )
    for _ in range(LIMITS["otp"].attempts + 3):
        allowed, _, retry_after = check(request, "otp")
        assert allowed is True
        assert retry_after == 0
    assert AuditEvent.objects.filter(action="ABUSE_OVERRIDE_CREATE").exists()


def test_counter_recovery_has_no_permanent_lockout():
    request = RequestFactory(REMOTE_ADDR="192.0.2.222").post("/api/v1/otp")
    request.user = type("Anonymous", (), {"is_authenticated": False})()
    for _ in range(LIMITS["otp"].attempts + 1):
        denied = check(request, "otp")
    assert denied[0] is False
    cache.clear()
    assert check(request, "otp")[0] is True
