from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from modules.audit.service import record_audit_event

from .models import AbuseOverride


@dataclass(frozen=True)
class Limit:
    attempts: int
    window_seconds: int


LIMITS = {
    "sign-in": Limit(10, 300),
    "otp": Limit(5, 600),
    "upload": Limit(20, 3600),
    "application": Limit(20, 86400),
    "search": Limit(120, 60),
    "export": Limit(3, 86400),
}


def escalation_delay(overage: int) -> int:
    return min(900, 2 ** min(max(overage, 0), 9))


def tightened(limit: Limit, anomaly_score: int) -> Limit:
    if anomaly_score < 1:
        return limit
    return Limit(max(1, limit.attempts // min(anomaly_score + 1, 4)), limit.window_seconds)


@transaction.atomic
def create_override(
    *, subject_token: str, action: str, reason_code: str, approved_by, expires_at
) -> AbuseOverride:
    if action not in LIMITS:
        raise ValidationError("Unknown protected action")
    if not reason_code.strip() or expires_at <= timezone.now():
        raise ValidationError("A reason and future expiry are required")
    override = AbuseOverride.objects.create(
        subject_token=subject_token,
        action=action,
        reason_code=reason_code,
        approved_by=approved_by,
        valid_from=timezone.now(),
        expires_at=expires_at,
    )
    record_audit_event(
        actor=approved_by,
        action="ABUSE_OVERRIDE_CREATE",
        target_type="abuse_override",
        target_id=str(override.id),
        outcome="ALLOWED",
        reason_code=reason_code,
    )
    return override


def active_override(*, subject_token: str, action: str) -> bool:
    now = timezone.now()
    return AbuseOverride.objects.filter(
        subject_token=subject_token,
        action=action,
        valid_from__lte=now,
        expires_at__gt=now,
        revoked_at__isnull=True,
    ).exists()
