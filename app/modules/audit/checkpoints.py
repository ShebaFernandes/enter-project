from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Protocol

from django.db import transaction

from .models import AuditCheckpoint, AuditEvent


class CheckpointStore(Protocol):
    def sign(self, digest: bytes) -> bytes: ...
    def put_locked(self, key: str, payload: bytes) -> None: ...


class AwsCheckpointStore:
    def __init__(self, *, kms_client, s3_client, kms_key_id: str, bucket: str) -> None:
        self.kms_client = kms_client
        self.s3_client = s3_client
        self.kms_key_id = kms_key_id
        self.bucket = bucket

    def sign(self, digest: bytes) -> bytes:
        response = self.kms_client.sign(
            KeyId=self.kms_key_id,
            Message=digest,
            MessageType="RAW",
            SigningAlgorithm="RSASSA_PSS_SHA_256",
        )
        return response["Signature"]

    def put_locked(self, key: str, payload: bytes) -> None:
        self.s3_client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=payload,
            ServerSideEncryption="aws:kms",
            SSEKMSKeyId=self.kms_key_id,
            ObjectLockMode="COMPLIANCE",
            ObjectLockRetainUntilDate=datetime.now(UTC) + timedelta(days=35),
        )


@dataclass(frozen=True)
class CheckpointUnavailable(RuntimeError):
    message: str = "Durable audit checkpoint unavailable"


@transaction.atomic
def create_daily_checkpoint(day: date, store: CheckpointStore) -> AuditCheckpoint:
    terminal = (
        AuditEvent.objects.filter(occurred_at__date__lte=day)
        .order_by("-occurred_at", "-id")
        .first()
    )
    terminal_hash = terminal.event_hash if terminal else hashlib.sha256(b"").hexdigest()
    payload = f"{day.isoformat()}:{terminal_hash}".encode()
    key = f"audit-checkpoints/{day.isoformat()}.sha256"
    try:
        signature = store.sign(payload)
        store.put_locked(key, payload + b"\n" + signature)
    except Exception as exc:
        raise CheckpointUnavailable() from exc
    return AuditCheckpoint.objects.create(
        checkpoint_date=day, terminal_hash=terminal_hash, signature=signature, object_key=key
    )
