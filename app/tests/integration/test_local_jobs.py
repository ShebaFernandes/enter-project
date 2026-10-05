from dataclasses import replace
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.core import mail
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.utils import timezone

from modules.communications.models import Notification
from modules.communications.service import queue_notification
from modules.operations.local_jobs import run_local_jobs
from modules.privacy.export_service import download_export
from modules.privacy.models import DataRightsRequest
from modules.privacy.services import create_rights_request

pytestmark = pytest.mark.django_db


def test_worker_completes_requested_export_and_sends_local_notification(profile_factory, settings):
    settings.EMAIL_HOST = "localhost"
    profile = profile_factory()
    request = create_rights_request(
        identity=profile.identity, profile=profile, values={"request_type": "EXPORT"}
    )
    notification, _ = queue_notification(
        destination="synthetic@example.test",
        channel="EMAIL",
        template_key="application-status",
        template_version="v1",
        consent_basis="APPLICATION_STATUS_UPDATES",
        idempotency_key="local-mail-test",
    )
    call_command("run_outbox_worker", once=True)
    request.refresh_from_db()
    notification.refresh_from_db()
    assert request.state == DataRightsRequest.State.COMPLETED
    exported_profile = download_export(identity=profile.identity, request=request)["profile"]
    assert isinstance(exported_profile, dict)
    assert exported_profile["id"] == str(profile.id)
    assert notification.state == Notification.State.SENT
    assert len(mail.outbox) == 1
    call_command("run_outbox_worker", once=True)
    assert len(mail.outbox) == 1


def test_notification_retry_respects_backoff_and_recovers(settings):
    settings.EMAIL_HOST = "localhost"
    notification, _ = queue_notification(
        destination="synthetic@example.test",
        channel="EMAIL",
        template_key="application-status",
        template_version="v1",
        consent_basis="APPLICATION_STATUS_UPDATES",
        idempotency_key="retry-test",
    )
    with patch("modules.operations.local_jobs.EmailMessage.send", side_effect=OSError):
        run_local_jobs()
    notification.refresh_from_db()
    assert notification.state == Notification.State.QUEUED
    assert notification.attempts == 1
    assert run_local_jobs() == 0
    notification.next_attempt_at = timezone.now() - timedelta(seconds=1)
    notification.save()
    run_local_jobs()
    notification.refresh_from_db()
    assert notification.state == Notification.State.SENT
    assert notification.attempts == 2


def test_export_failure_is_visible_without_stalling_other_jobs(profile_factory):
    profile = profile_factory()
    request = create_rights_request(
        identity=profile.identity, profile=profile, values={"request_type": "EXPORT"}
    )
    with patch("modules.operations.local_jobs.generate_export", side_effect=OSError):
        run_local_jobs()
    request.refresh_from_db()
    assert request.state == DataRightsRequest.State.FAILED
    assert request.export.state == "FAILED"
    assert request.failure_category == "EXPORT_UNAVAILABLE"


def test_development_worker_rejects_production(settings):
    settings.ENV = replace(settings.ENV, app_env="production")
    with pytest.raises(ImproperlyConfigured):
        call_command("run_outbox_worker", once=True)


def test_due_deletion_waits_for_deadline_and_legal_hold(profile_factory):
    from types import SimpleNamespace
    from uuid import uuid4

    from modules.operations.crypto import encrypt
    from modules.privacy.models import LegalHold

    profile = profile_factory()
    request = create_rights_request(
        identity=profile.identity,
        profile=profile,
        values={"request_type": "DELETE", "confirm_consequences": True},
        step_up_evidence=SimpleNamespace(id=uuid4()),
    )
    run_local_jobs()
    request.refresh_from_db()
    assert request.state == DataRightsRequest.State.PENDING
    request.expected_completion_at = timezone.now() - timedelta(seconds=1)
    request.save()
    hold = LegalHold.objects.create(
        profile=profile,
        authority_reference="synthetic-review",
        approver=profile.identity,
        encrypted_rationale=encrypt("Synthetic hold"),
        starts_at=timezone.now() - timedelta(days=1),
        review_at=timezone.now() + timedelta(days=1),
    )
    run_local_jobs()
    request.refresh_from_db()
    assert request.state == DataRightsRequest.State.HELD
    hold.ends_at = timezone.now() - timedelta(seconds=1)
    hold.save()
    run_local_jobs()
    request.refresh_from_db()
    profile.refresh_from_db()
    assert request.state == DataRightsRequest.State.COMPLETED
    assert profile.profile_state == "DELETED"
