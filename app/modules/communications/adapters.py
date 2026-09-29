from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from typing import Protocol

from django.conf import settings


class DeliveryUnavailable(RuntimeError):
    pass


class DeliveryAdapter(Protocol):
    def send(self, *, destination: str, template_key: str, template_version: str) -> str: ...


@dataclass(frozen=True)
class SesAdapter:
    client: object
    source: str

    def send(self, *, destination: str, template_key: str, template_version: str) -> str:
        response = self.client.send_templated_email(
            Source=self.source,
            Destination={"ToAddresses": [destination]},
            Template=template_key,
            TemplateData='{"version":"' + template_version + '"}',
        )
        return str(response["MessageId"])


class WhatsAppAdapter:
    def send(self, **_kwargs) -> str:
        if not settings.ENV.whatsapp_enabled:
            raise DeliveryUnavailable("WHATSAPP_NOT_APPROVED")
        raise DeliveryUnavailable("WHATSAPP_PROVIDER_NOT_CONFIGURED")


def verify_callback_signature(*, payload: bytes, signature: str, secret: bytes) -> bool:
    expected = hmac.new(secret, payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
