from dataclasses import dataclass


@dataclass(frozen=True)
class Limit:
    attempts: int
    window_seconds: int


LIMITS = {
    "sign-in": Limit(10, 300),
    "otp": Limit(5, 600),
    "upload": Limit(20, 3600),
    "application": Limit(10, 3600),
    "search": Limit(120, 60),
    "export": Limit(3, 86400),
}


def escalation_delay(overage: int) -> int:
    return min(900, 2 ** min(max(overage, 0), 9))


def tightened(limit: Limit, anomaly_score: int) -> Limit:
    if anomaly_score < 1:
        return limit
    return Limit(max(1, limit.attempts // min(anomaly_score + 1, 4)), limit.window_seconds)
