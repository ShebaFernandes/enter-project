from __future__ import annotations

import hashlib
from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from modules.candidate.models import CandidateProfile
from modules.operations.crypto import blind_index
from modules.operations.outbox import enqueue

from .audit import audit_rights_action
from .models import (
    ActiveProcessRetentionException,
    DataRightsRequest,
    DeletionLedger,
)


@transaction.atomic
def begin_deletion(*, identity, profile: CandidateProfile, request: DataRightsRequest) -> None:
    if profile.identity_id != identity.id or request.profile_id != profile.id:
        raise PermissionDenied("Deletion request unavailable")
    if request.step_up_evidence_id is None or request.consequence_confirmed_at is None:
        raise ValidationError("Verified deletion confirmation is required.")
    profile.profile_state = CandidateProfile.State.DELETION_PENDING
    profile.version += 1
    profile.save(update_fields=("profile_state", "version", "updated_at"))
    enqueue(
        aggregate_type="candidate_profile",
        aggregate_id=profile.id,
        aggregate_version=profile.version,
        event_type="rights.deletion_confirmed.v1",
        payload={"candidate_profile_id": str(profile.id), "rights_request_id": str(request.id)},
        idempotency_key=f"deletion-confirmed:{request.id}",
        actor_id=identity.id,
    )


@transaction.atomic
def create_active_process_exception(
    *,
    profile,
    application,
    policy_version: str,
    legal_basis: str,
    retained_data_scope: list[str],
    review_date,
    terminating_event: str,
    approved_by,
    audit_references: list[str],
) -> ActiveProcessRetentionException:
    item = ActiveProcessRetentionException(
        profile=profile,
        application=application,
        policy_version=policy_version,
        legal_basis=legal_basis,
        retained_data_scope=retained_data_scope,
        start_date=timezone.now(),
        review_date=review_date,
        terminating_event=terminating_event,
        approved_by=approved_by,
        audit_references=audit_references,
    )
    item.full_clean()
    item.save()
    return item


@transaction.atomic
def resolve_exception(*, item: ActiveProcessRetentionException, actor, revoked: bool = False):
    if item.lifecycle_state not in {
        ActiveProcessRetentionException.State.ACTIVE,
        ActiveProcessRetentionException.State.UNDER_REVIEW,
    }:
        raise ValidationError("Retention exception is already closed.")
    item.lifecycle_state = (
        ActiveProcessRetentionException.State.REVOKED
        if revoked
        else ActiveProcessRetentionException.State.RESOLVED
    )
    item.resolution_date = timezone.now()
    item.version += 1
    item.save(update_fields=("lifecycle_state", "resolution_date", "version"))
    enqueue(
        aggregate_type="active_process_retention_exception",
        aggregate_id=item.id,
        aggregate_version=item.version,
        event_type="rights.active_process_exception_changed.v1",
        payload={"exception_id": str(item.id), "version": item.version},
        idempotency_key=f"retention-exception:{item.id}:{item.version}",
        actor_id=actor.id,
    )
    remaining = item.profile.retention_exceptions.filter(
        lifecycle_state__in=[
            ActiveProcessRetentionException.State.ACTIVE,
            ActiveProcessRetentionException.State.UNDER_REVIEW,
        ]
    ).exists()
    if not remaining:
        held_deletions = item.profile.rights_requests.filter(
            request_type=DataRightsRequest.RequestType.DELETE,
            state=DataRightsRequest.State.HELD,
        )
        for deletion in held_deletions:
            deletion.state = DataRightsRequest.State.IN_PROGRESS
            deletion.safe_detail = "Retention exception ended; deletion resumed"
            deletion.save(update_fields=("state", "safe_detail"))
            complete_due_deletion(deletion.id, force_due=True)
    return item


@transaction.atomic
def complete_due_deletion(request_id, *, force_due: bool = False) -> bool:
    request = (
        DataRightsRequest.objects.select_for_update()
        .select_related("profile__identity")
        .get(pk=request_id)
    )
    if request.request_type != DataRightsRequest.RequestType.DELETE:
        raise ValidationError("Not a deletion request.")
    if not force_due and request.expected_completion_at > timezone.now():
        return False
    profile = request.profile
    active_exceptions = profile.retention_exceptions.filter(
        lifecycle_state__in=["ACTIVE", "UNDER_REVIEW"]
    )
    active_holds = profile.legal_holds.filter(starts_at__lte=timezone.now()).filter(
        models.Q(ends_at__isnull=True) | models.Q(ends_at__gt=timezone.now())
    )
    if active_exceptions.exists() or active_holds.exists():
        request.state = DataRightsRequest.State.HELD
        request.safe_detail = "Deletion is held for a limited identified scope"
        request.save(update_fields=("state", "safe_detail"))
        return False
    profile.skills.all().delete()
    profile.contacts.all().delete()
    profile.links.all().delete()
    profile.employment_history.all().delete()
    profile.evidence.all().delete()
    profile.resumes.all().delete()
    profile.visibility_rules.all().delete()
    profile.consents.all().delete()
    profile.full_name_ciphertext = b""
    profile.location = {}
    profile.headline = ""
    profile.current_role = ""
    profile.current_company = ""
    profile.role_categories = []
    profile.preferred_locations = []
    profile.work_arrangements = []
    profile.meaningful_work = ""
    profile.notice_period = ""
    profile.compensation_ciphertext = None
    profile.contact_preferences = {}
    profile.profile_state = CandidateProfile.State.DELETED
    profile.version += 1
    profile.save()
    now = timezone.now()
    request.state = DataRightsRequest.State.COMPLETED
    request.completed_at = now
    request.safe_detail = "Identifiable profile data deleted"
    request.save(update_fields=("state", "completed_at", "safe_detail"))
    token = blind_index(str(profile.identity_id), purpose="deletion-ledger")
    evidence = hashlib.sha256(f"{profile.id}:{now.isoformat()}".encode()).hexdigest()
    DeletionLedger.objects.update_or_create(
        subject_token=token,
        defaults={
            "deletion_scope": ["profile", "resume", "employment", "visibility", "consent"],
            "source_completion": {"primary": "COMPLETED", "search": "PENDING_REPLAY"},
            "backup_cutoff": now + timedelta(days=35),
            "replay_status": "PENDING",
            "completed_at": now,
            "evidence_hash": evidence,
        },
    )
    audit_rights_action(
        actor=profile.identity,
        request=request,
        action="RIGHTS_DELETION_COMPLETED",
        metadata={"scope_categories": ["profile", "resume", "employment", "visibility", "consent"]},
    )
    return True


from django.db import models  # noqa: E402
