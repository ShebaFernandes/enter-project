from django.db import transaction
from django.utils import timezone

from modules.operations.outbox import enqueue
from modules.operations.workers import claim_once

from .finding_evaluators import evaluate_employment_record
from .models import CandidateFinding, CandidateProfile


@transaction.atomic
def handle_employment_history_changed(
    payload: dict, *, aggregate_version: int, actor_id=None, event_id=None
):
    if event_id is not None and not claim_once(event_id, "candidate-finding-evaluator-v1"):
        return None
    profile = CandidateProfile.objects.get(pk=payload["candidate_profile_id"])
    changed_ids = {str(item["record_id"]) for item in payload.get("records", [])}
    present = {
        str(record.id): record for record in profile.employment_history.filter(id__in=changed_ids)
    }
    for record_id in changed_ids - set(present):
        CandidateFinding.objects.filter(
            profile=profile, source_record_id=record_id, superseded_at__isnull=True
        ).update(superseded_at=timezone.now())
    for record in present.values():
        evaluate_employment_record(record)
    enqueue(
        aggregate_type="candidate_profile",
        aggregate_id=profile.id,
        aggregate_version=aggregate_version,
        event_type="candidate.findings_recalculated.v1",
        payload={
            "candidate_profile_id": str(profile.id),
            "changed_record_ids": sorted(changed_ids),
        },
        idempotency_key=f"candidate-findings:{profile.id}:{aggregate_version}",
        actor_id=actor_id,
    )
    return profile
