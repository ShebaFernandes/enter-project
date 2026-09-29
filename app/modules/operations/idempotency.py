from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from .concurrency import canonical_hash
from .models import IdempotencyRecord


class IdempotencyConflict(Exception):
    pass


@transaction.atomic
def reserve(actor_key: str, key: str, request_body: object) -> tuple[IdempotencyRecord, bool]:
    request_hash = canonical_hash(request_body)
    record, created = IdempotencyRecord.objects.select_for_update().get_or_create(
        actor_key=actor_key,
        key=key,
        defaults={"request_hash": request_hash, "expires_at": timezone.now() + timedelta(hours=24)},
    )
    if record.request_hash != request_hash:
        raise IdempotencyConflict("Idempotency key reused with a different request")
    return record, created


def complete(record: IdempotencyRecord, status_code: int, response_body: object) -> None:
    record.response_status = status_code
    record.response_body = response_body
    record.save(update_fields=["response_status", "response_body"])


@transaction.atomic
def execute(request, operation) -> Response:
    key = request.headers.get("Idempotency-Key", "")
    if not 16 <= len(key) <= 200:
        raise ValidationError({"Idempotency-Key": "A 16-200 character key is required."})
    actor_key = str(request.user.pk) if request.user.is_authenticated else "anonymous"
    record, created = reserve(actor_key, key, request.data)
    if not created:
        if record.response_status is None:
            raise IdempotencyConflict("An operation with this key is still pending")
        return Response(record.response_body, status=record.response_status)
    response = operation()
    complete(record, response.status_code, response.data)
    return response
