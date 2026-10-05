"""Development job dispatch; external delivery stays inside the local mail sink."""

from contextlib import contextmanager

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import EmailMessage
from django.db import connection, transaction
from django.db.models import Q
from django.utils import timezone

from modules.communications.adapters import DeliveryUnavailable, WhatsAppAdapter
from modules.communications.models import Notification
from modules.communications.workers import deliver
from modules.privacy.deletion_service import complete_due_deletion
from modules.privacy.export_service import expire_exports, generate_export
from modules.privacy.models import DataRightsRequest, RightsExport


def require_local_worker():
    if settings.ENV.app_env not in {"local", "test"}:
        raise ImproperlyConfigured("The development worker cannot run in production")


@contextmanager
def job_context(*, actor_id=None, tenant_id=None):
    with transaction.atomic():
        previous = None
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT current_setting('app.identity_id', true), "
                    "current_setting('app.tenant_id', true)"
                )
                previous = cursor.fetchone()
                cursor.execute(
                    "SELECT set_config('app.identity_id', %s, true), "
                    "set_config('app.tenant_id', %s, true)",
                    [str(actor_id or ""), str(tenant_id or "")],
                )
        try:
            yield
        finally:
            if previous is not None and not connection.needs_rollback:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT set_config('app.identity_id', %s, true), "
                        "set_config('app.tenant_id', %s, true)",
                        [previous[0] or "", previous[1] or ""],
                    )


class LocalEmailAdapter:
    def send(self, *, destination: str, template_key: str, template_version: str) -> str:
        require_local_worker()
        if settings.EMAIL_HOST not in {"mail", "localhost", "127.0.0.1"}:
            raise DeliveryUnavailable("LOCAL_MAIL_SINK_REQUIRED")
        message = EmailMessage(
            subject="An update is available in Enter",
            body=(
                "An update is available in your Enter account. "
                "Sign in to review the current information.\n"
            ),
            from_email="Enter <notifications@enter.example.test>",
            to=[destination],
        )
        if message.send(fail_silently=False) != 1:
            raise DeliveryUnavailable("LOCAL_MAIL_DELIVERY_FAILED")
        return "local-mail"


def dispatch_local_event(envelope):
    require_local_worker()
    with job_context(actor_id=envelope["actor_id"], tenant_id=envelope["tenant_id"]):
        if envelope["event_type"] == "resume.processing_requested.v1":
            from modules.candidate.resume_processing import process_resume

            process_resume(envelope["payload"]["resume_id"], envelope["actor_id"])
        elif envelope["event_type"] == "profile.employment_history_changed.v1":
            from modules.candidate.finding_events import handle_employment_history_changed

            handle_employment_history_changed(
                envelope["payload"],
                aggregate_version=envelope["aggregate"]["version"],
                actor_id=envelope["actor_id"],
                event_id=envelope["event_id"],
            )
        # Notifications are durable records polled below, including scheduled retries.
        # Remaining domain events have no additional local consumer.


def run_local_jobs(limit=100):
    require_local_worker()
    processed = 0
    pending = list(
        RightsExport.objects.filter(
            state=RightsExport.State.PENDING, request__state=DataRightsRequest.State.PENDING
        ).values_list("id", "request__profile__identity_id")[:limit]
    )
    for export_id, identity_id in pending:
        with job_context(actor_id=identity_id):
            export = RightsExport.objects.select_for_update().get(pk=export_id)
            if export.state != RightsExport.State.PENDING:
                continue
            try:
                with transaction.atomic():
                    generate_export(export_id)
            except Exception:
                export.state = RightsExport.State.FAILED
                export.failure_category = "EXPORT_UNAVAILABLE"
                export.save(update_fields=("state", "failure_category"))
                DataRightsRequest.objects.filter(pk=export.request_id).update(
                    state=DataRightsRequest.State.FAILED,
                    failure_category="EXPORT_UNAVAILABLE",
                    safe_detail="Export could not be generated. Contact support to retry.",
                )
            processed += 1
    expire_exports()
    due_deletions = list(
        DataRightsRequest.objects.filter(
            request_type=DataRightsRequest.RequestType.DELETE,
            state__in=["PENDING", "IN_PROGRESS", "HELD"],
            consequence_confirmed_at__isnull=False,
            expected_completion_at__lte=timezone.now(),
        ).values_list("id", "profile__identity_id")[:limit]
    )
    for request_id, identity_id in due_deletions:
        with job_context(actor_id=identity_id):
            processed += int(complete_due_deletion(request_id))
    due = list(
        Notification.objects.filter(state=Notification.State.QUEUED)
        .filter(Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=timezone.now()))
        .values_list("id", "tenant_id")[:limit]
    )
    for notification_id, tenant_id in due:
        with job_context(tenant_id=tenant_id):
            notification = Notification.objects.select_for_update().get(pk=notification_id)
            if notification.next_attempt_at and notification.next_attempt_at > timezone.now():
                continue
            adapter = LocalEmailAdapter() if notification.channel == "EMAIL" else WhatsAppAdapter()
            deliver(notification_id, adapter=adapter)
            processed += 1
    return processed
