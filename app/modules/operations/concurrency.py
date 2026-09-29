import hashlib
import json

from rest_framework.exceptions import APIException


def strong_etag(object_id: object, version: int) -> str:
    digest = hashlib.sha256(f"{object_id}:{version}".encode()).hexdigest()
    return f'"{digest}"'


class StaleWrite(APIException):
    status_code = 409
    default_code = "stale_write"

    def __init__(
        self,
        *,
        current: dict[str, object],
        attempted: dict[str, object],
        object_id: object,
        version: int,
    ) -> None:
        changed = sorted(key for key in attempted if attempted.get(key) != current.get(key))
        self.reconciliation = {
            "current": current,
            "attempted": attempted,
            "changed_fields": changed,
            "current_etag": strong_etag(object_id, version),
        }
        super().__init__(self.reconciliation)  # type: ignore[arg-type]


def require_match(
    if_match: str | None,
    *,
    object_id: object,
    version: int,
    current: dict[str, object],
    attempted: dict[str, object],
) -> None:
    if if_match != strong_etag(object_id, version):
        raise StaleWrite(current=current, attempted=attempted, object_id=object_id, version=version)


def require_if_match(if_match: str | None, instance, attempted: dict[str, object]) -> None:
    current = {key: getattr(instance, key) for key in attempted if hasattr(instance, key)}
    require_match(
        if_match,
        object_id=instance.pk,
        version=instance.version,
        current=current,
        attempted=attempted,
    )


def canonical_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
