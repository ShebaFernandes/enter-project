from __future__ import annotations

from modules.communications.models import Notification
from modules.communications.service import candidate_projection

from .application_models import Application


def _timestamp(value):
    if value is None:
        return None
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def candidate_applications(*, profile):
    return (
        Application.objects.filter(candidate_profile_id=profile.id)
        .select_related("opening")
        .prefetch_related("history")
        .order_by("-submitted_at", "-created_at")
    )


def application_data(application: Application) -> dict[str, object]:
    notifications = Notification.objects.filter(application_id=application.id).order_by(
        "created_at"
    )
    history = [
        {
            "candidate_status": item.published_candidate_status,
            "updated_at": _timestamp(item.occurred_at),
        }
        for item in application.history.all().order_by("occurred_at")
        if item.published_candidate_status
    ]
    return {
        "id": str(application.id),
        "opening_id": str(application.opening_id),
        "resume_id": str(application.resume_id) if application.resume_id else None,
        "opening_title": application.opening.title,
        "candidate_status": application.candidate_status,
        "status_updated_at": _timestamp(application.status_published_at or application.updated_at),
        "submitted_at": _timestamp(application.submitted_at),
        "withdrawn_at": _timestamp(application.withdrawn_at),
        "notification_preferences": {
            "email": application.notify_email,
            "whatsapp": application.notify_whatsapp,
        },
        "notification_states": [candidate_projection(item) for item in notifications],
        "status_history": history,
        "version": application.version,
    }
