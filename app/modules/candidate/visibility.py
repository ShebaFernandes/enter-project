from __future__ import annotations

from datetime import timedelta
from typing import cast
from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from modules.audit.service import record_audit_event
from modules.operations.concurrency import require_match
from modules.operations.outbox import enqueue

from .models import CandidateProfile, ConsentRecord, VisibilityRule
from .services import current_visibility, profile_data


@transaction.atomic
def replace_visibility(
    *, identity, profile: CandidateProfile, if_match: str | None, values: dict[str, object]
) -> VisibilityRule:
    profile = CandidateProfile.objects.select_for_update().get(pk=profile.pk, identity=identity)
    require_match(
        if_match,
        object_id=profile.id,
        version=profile.version,
        current=cast(dict[str, object], profile_data(profile).get("visibility", {})),
        attempted=values,
    )
    consent = ConsentRecord.objects.filter(
        pk=cast(UUID, values["consent_record_id"]),
        profile=profile,
        withdrawn_at__isnull=True,
        expires_at__gt=timezone.now(),
    ).first()
    mode = str(values["mode"])
    approved = [str(value) for value in values.get("approved_tenant_ids", [])]
    preferences = cast(dict[str, object], values.get("matching_preferences", {}))
    if mode == VisibilityRule.Mode.APPROVED_RECRUITERS and not approved:
        raise ValidationError({"approved_tenant_ids": "An explicit audience is required."})
    if mode == VisibilityRule.Mode.MATCHING_ROLES and not preferences:
        raise ValidationError({"matching_preferences": "Matching preferences are required."})
    consent_id = cast(UUID, values["consent_record_id"])
    if consent is None and ConsentRecord.objects.filter(pk=consent_id).exists():
        raise PermissionDenied("Consent unavailable")
    if consent is None:
        # The visibility PUT is the affirmative action. Its client-generated consent ID makes
        # retries stable without creating a second, undocumented consent endpoint.
        consent = ConsentRecord.objects.create(
            id=consent_id,
            profile=profile,
            purpose="RECRUITING_DISCOVERY",
            field_scope=["profile", "employment_history", "skills", "resume"],
            audience_scope={
                "approved_tenant_ids": approved,
                "matching_preferences": preferences,
            },
            notice_version="candidate-discovery-v1",
            affirmative_action="VISIBILITY_SAVE",
            source_request_id=f"visibility:{profile.id}:{profile.version + 1}",
            expires_at=timezone.now() + timedelta(days=365),
        )
    if consent.purpose != "RECRUITING_DISCOVERY":
        raise PermissionDenied("Consent unavailable")
    prior = current_visibility(profile)
    if prior is not None:
        prior.superseded_at = timezone.now()
        prior.save(update_fields=("superseded_at",))
    rule = VisibilityRule(
        profile=profile,
        mode=mode,
        approved_tenant_ids=approved,
        matching_preferences=preferences,
        consent_record=consent,
        actor=identity,
        version=(prior.version + 1 if prior else 1),
    )
    rule.full_clean()
    rule.save()
    if mode == VisibilityRule.Mode.NOT_LOOKING:
        profile.profile_state = CandidateProfile.State.HIDDEN
    profile.version += 1
    profile.last_candidate_activity_at = timezone.now()
    profile.save(
        update_fields=("profile_state", "version", "last_candidate_activity_at", "updated_at")
    )
    enqueue(
        aggregate_type="candidate_profile",
        aggregate_id=profile.id,
        aggregate_version=profile.version,
        event_type="profile.visibility_changed.v1",
        payload={"candidate_profile_id": str(profile.id), "mode": mode},
        idempotency_key=f"visibility:{profile.id}:{profile.version}",
        actor_id=identity.id,
    )
    record_audit_event(
        actor=identity,
        action="CANDIDATE_VISIBILITY_CHANGE",
        target_type="candidate_profile",
        target_id=str(profile.id),
        outcome="ALLOWED",
        metadata={"mode": mode, "version": profile.version},
    )
    return rule


@transaction.atomic
def withdraw_consent(*, identity, profile: CandidateProfile) -> None:
    now = timezone.now()
    ConsentRecord.objects.filter(profile=profile, withdrawn_at__isnull=True).update(
        withdrawn_at=now, version=models.F("version") + 1
    )
    VisibilityRule.objects.filter(profile=profile, superseded_at__isnull=True).update(
        superseded_at=now
    )
    profile.profile_state = CandidateProfile.State.HIDDEN
    profile.version += 1
    profile.save(update_fields=("profile_state", "version", "updated_at"))
    enqueue(
        aggregate_type="candidate_profile",
        aggregate_id=profile.id,
        aggregate_version=profile.version,
        event_type="profile.visibility_changed.v1",
        payload={"candidate_profile_id": str(profile.id), "mode": "HIDDEN"},
        idempotency_key=f"consent-withdrawn:{profile.id}:{profile.version}",
        actor_id=identity.id,
    )


from django.db import models  # noqa: E402  # keep F close to the transactional update
