from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from modules.audit.service import record_audit_event
from modules.operations.crypto import decrypt

from .adapters import DeliveryAdapter
from .models import Notification, NotificationDeadLetter

MAX_ATTEMPTS = 5
MAX_DELIVERY_AGE = timedelta(hours=24)


@transaction.atomic
def deliver(notification_id, *, adapter: DeliveryAdapter) -> Notification:
    notification = Notification.objects.select_for_update().get(pk=notification_id)
    if notification.state in {
        Notification.State.SENT,
        Notification.State.CANCELLED,
        Notification.State.FAILED,
    }:
        return notification
    if notification.application_id:
        from modules.recruiting.models import Application

        application = (
            Application.objects.select_for_update()
            .filter(pk=notification.application_id, tenant_id=str(notification.tenant_id))
            .first()
            if notification.tenant_id is not None
            else None
        )
        allowed = application is not None and application.state != Application.State.WITHDRAWN
        if application is not None:
            allowed = allowed and (
                application.notify_email
                if notification.channel == "EMAIL"
                else application.notify_whatsapp
            )
        if not allowed:
            notification.state = Notification.State.CANCELLED
            notification.next_attempt_at = None
            notification.save(update_fields=("state", "next_attempt_at", "updated_at"))
            return notification
    now = timezone.now()
    if now - notification.created_at >= MAX_DELIVERY_AGE or notification.attempts >= MAX_ATTEMPTS:
        return _dead_letter(notification, "DELIVERY_WINDOW_EXHAUSTED")
    if notification.first_attempt_at is None:
        notification.first_attempt_at = now
    notification.state = Notification.State.SENDING
    notification.attempts += 1
    notification.save(update_fields=("state", "attempts", "first_attempt_at", "updated_at"))
    try:
        reference = adapter.send(
            destination=decrypt(bytes(notification.destination_ciphertext)),
            template_key=notification.template_key,
            template_version=notification.template_version,
        )
    except Exception as exc:
        if (
            notification.attempts >= MAX_ATTEMPTS
            or now - notification.created_at >= MAX_DELIVERY_AGE
        ):
            return _dead_letter(notification, type(exc).__name__.upper()[:80])
        notification.state = Notification.State.QUEUED
        notification.next_attempt_at = now + timedelta(minutes=min(360, 2**notification.attempts))
        notification.save(update_fields=("state", "next_attempt_at", "updated_at"))
        return notification
    notification.state = Notification.State.SENT
    notification.provider_reference = reference
    notification.next_attempt_at = None
    notification.terminal_error_category = ""
    notification.save(
        update_fields=(
            "state",
            "provider_reference",
            "next_attempt_at",
            "terminal_error_category",
            "updated_at",
        )
    )
    return notification


def _dead_letter(notification: Notification, category: str) -> Notification:
    notification.state = Notification.State.FAILED
    notification.terminal_error_category = category
    notification.next_attempt_at = None
    notification.save(
        update_fields=(
            "state",
            "terminal_error_category",
            "next_attempt_at",
            "updated_at",
        )
    )
    NotificationDeadLetter.objects.get_or_create(
        notification=notification, defaults={"failure_category": category}
    )
    record_audit_event(
        actor=None,
        tenant_id=notification.tenant_id,
        action="NOTIFICATION_DEAD_LETTER",
        target_type="notification",
        target_id=str(notification.id),
        outcome="FAILED",
        reason_code=category,
    )
    return notification


@transaction.atomic
def redrive(dead_letter_id, *, actor) -> Notification:
    dead_letter = NotificationDeadLetter.objects.select_for_update().get(pk=dead_letter_id)
    if dead_letter.redriven_at is not None:
        return dead_letter.notification
    notification = dead_letter.notification
    notification.state = Notification.State.QUEUED
    notification.attempts = 0
    notification.first_attempt_at = None
    notification.next_attempt_at = timezone.now()
    notification.terminal_error_category = ""
    notification.save()
    dead_letter.redriven_at = timezone.now()
    dead_letter.redriven_by_id = actor.id
    dead_letter.save(update_fields=("redriven_at", "redriven_by_id"))
    record_audit_event(
        actor=actor,
        tenant_id=notification.tenant_id,
        action="NOTIFICATION_DLQ_REDRIVE",
        target_type="notification",
        target_id=str(notification.id),
        outcome="ALLOWED",
    )
    return notification
