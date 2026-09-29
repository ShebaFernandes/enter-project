from __future__ import annotations

import base64
import hashlib
import hmac
import json

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder


class CryptoError(Exception):
    pass


def _keys() -> dict[str, bytes]:
    return dict(settings.ENV.field_encryption_keys)


def encrypt(value: str) -> bytes:
    version, key = settings.ENV.field_encryption_keys[0]
    token = Fernet(base64.urlsafe_b64encode(key)).encrypt(value.encode())
    return version.encode() + b":" + token


def decrypt(value: bytes) -> str:
    try:
        version, token = value.split(b":", 1)
        key = _keys()[version.decode()]
        return Fernet(base64.urlsafe_b64encode(key)).decrypt(token).decode()
    except (ValueError, KeyError, InvalidToken, UnicodeDecodeError) as exc:
        raise CryptoError("Encrypted value cannot be decrypted") from exc


def blind_index(value: str, *, purpose: str) -> bytes:
    normalized = " ".join(value.casefold().split())
    material = f"{purpose}\0{normalized}".encode()
    return hmac.new(settings.ENV.email_lookup_key, material, hashlib.sha256).digest()


def safe_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        cls=DjangoJSONEncoder,
    )
