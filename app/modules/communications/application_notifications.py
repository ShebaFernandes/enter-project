from __future__ import annotations

from modules.audit.service import record_audit_event
from modules.candidate.models import CandidateContact, CandidateProfile
from modules.operations.crypto import decrypt

from .models import Notification
from .service import candidate_projection, queue_notification


def queue_application_status_notifications(
    *, application, channels: list[str], candidate_status: str, request_key: str
) -> list[dict[str, object]]:
    profile = CandidateProfile.objects.select_related("identity").get(
        pk=application.candidate_profile_id
    )
    permitted = {
        "EMAIL": application.notify_email,
        "WHATSAPP": application.notify_whatsapp,
    }
    destinations: dict[str, str] = {}
    if permitted["EMAIL"]:
        destinations["EMAIL"] = decrypt(bytes(profile.identity.email_ciphertext))
    if permitted["WHATSAPP"]:
        contact = CandidateContact.objects.filter(profile=profile, channel="WHATSAPP").first()
        if contact is not None and contact.verified_at is not None:
            destinations["WHATSAPP"] = decrypt(bytes(contact.value_ciphertext))
    states: list[dict[str, object]] = []
    for channel in channels:
        if not permitted.get(channel, False):
            continue
        destination = destinations.get(channel)
        if not destination:
            states.append(
                {
                    "id": f"unavailable-{channel.casefold()}",
                    "channel": channel,
                    "state": "FAILED",
                    "safe_error": "DESTINATION_UNAVAILABLE",
                }
            )
            continue
        notification, _ = queue_notification(
            destination=destination,
            channel=channel,
            template_key="application-status",
            template_version="v1",
            consent_basis="APPLICATION_STATUS_UPDATES",
            idempotency_key=f"application-status:{request_key}:{channel}",
            tenant_id=application.tenant_id,
            candidate_profile_id=application.candidate_profile_id,
            application_id=application.id,
        )
        record_audit_event(
            actor=None,
            tenant_id=application.tenant_id,
            action="APPLICATION_NOTIFICATION_QUEUED",
            target_type="notification",
            target_id=str(notification.id),
            outcome="ALLOWED",
            purpose_code="APPLICATION_STATUS_UPDATES",
            metadata={
                "application_id": str(application.id),
                "channel": channel,
                "candidate_status": candidate_status,
            },
        )
        states.append(candidate_projection(notification))
    return states


def safe_failed_projection(channels: list[str]) -> list[dict[str, object]]:
    return [
        {
            "id": f"failed-{channel.casefold()}",
            "channel": channel,
            "state": Notification.State.FAILED,
            "safe_error": "DELIVERY_UNAVAILABLE",
        }
        for channel in channels
    ]
