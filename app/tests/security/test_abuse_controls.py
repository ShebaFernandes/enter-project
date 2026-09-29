from django.test import RequestFactory

from modules.abuse.policy import LIMITS, escalation_delay, tightened
from modules.abuse.service import check


def test_every_sensitive_action_has_a_balanced_limit():
    assert set(LIMITS) == {"sign-in", "otp", "upload", "application", "search", "export"}
    assert all(item.attempts > 0 and item.window_seconds > 0 for item in LIMITS.values())


def test_delay_escalates_but_never_permanently_locks():
    assert escalation_delay(3) > escalation_delay(1)
    assert escalation_delay(100) <= 900


def test_anomaly_tightening_reduces_allowance():
    assert tightened(LIMITS["search"], 2).attempts < LIMITS["search"].attempts


def test_threshold_returns_retry_after():
    request = RequestFactory(REMOTE_ADDR="198.51.100.7").post("/api/v1/otp")
    request.user = type("Anonymous", (), {"is_authenticated": False})()
    results = [check(request, "otp") for _ in range(LIMITS["otp"].attempts + 1)]
    assert results[-1][0] is False
    assert results[-1][2] > 0
