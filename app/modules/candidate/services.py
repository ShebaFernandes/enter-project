from __future__ import annotations

from collections.abc import Iterable
from datetime import timedelta
from typing import cast

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from modules.audit.service import record_audit_event
from modules.identity.models import IdentityCapability
from modules.operations.concurrency import require_match
from modules.operations.crypto import decrypt, encrypt, safe_json
from modules.operations.outbox import enqueue

from .models import CandidateProfile, CandidateSkill, EmploymentRecord, ProfileLink
from .serializers import employment_record_data


def require_candidate(identity) -> None:
    if (
        identity.email_verified_at is None
        or not IdentityCapability.objects.filter(
            identity=identity,
            role=IdentityCapability.Role.CANDIDATE,
            revoked_at__isnull=True,
        ).exists()
    ):
        raise PermissionDenied("Verified candidate access required")


def profile_for(identity, *, create: bool = True) -> CandidateProfile:
    require_candidate(identity)
    profile = CandidateProfile.objects.filter(identity=identity).first()
    if profile is None and create:
        profile = CandidateProfile.objects.create(identity=identity)
    if profile is None:
        raise CandidateProfile.DoesNotExist
    return profile


def current_visibility(profile: CandidateProfile):
    return profile.visibility_rules.filter(superseded_at__isnull=True).first()


def profile_data(profile: CandidateProfile) -> dict[str, object]:
    visibility = current_visibility(profile)
    compensation = None
    if profile.compensation_ciphertext:
        import json

        compensation = json.loads(decrypt(bytes(profile.compensation_ciphertext)))
    try:
        full_name = (
            decrypt(bytes(profile.full_name_ciphertext)) if profile.full_name_ciphertext else ""
        )
    except Exception:  # encrypted storage failure fails closed at the view boundary
        raise PermissionDenied("Profile unavailable") from None
    return {
        "id": profile.id,
        "full_name": full_name,
        "location": profile.location,
        "headline": profile.headline or None,
        "current_role": profile.current_role or None,
        "current_company": profile.current_company or None,
        "experience_years": profile.experience_years,
        "skills": list(profile.skills.values_list("display_name", flat=True)),
        "employment_history": [
            employment_record_data(item) for item in profile.employment_history.all()
        ],
        "role_categories": profile.role_categories,
        "preferred_locations": profile.preferred_locations,
        "work_arrangements": profile.work_arrangements,
        "meaningful_work": profile.meaningful_work or None,
        "notice_period": profile.notice_period or None,
        "availability_date": profile.availability_date,
        "compensation": compensation,
        "professional_links": list(profile.links.values_list("normalized_url", flat=True)),
        "contact_preferences": profile.contact_preferences,
        "profile_state": profile.profile_state,
        "visibility": {
            "mode": visibility.mode if visibility else "NOT_LOOKING",
            "approved_tenant_ids": visibility.approved_tenant_ids if visibility else [],
            "matching_preferences": visibility.matching_preferences if visibility else {},
            "version": visibility.version if visibility else 1,
        },
        "version": profile.version,
    }


def _date_precision(value, state: str) -> str:
    if value is None or state in {
        EmploymentRecord.ValueState.AMBIGUOUS,
        EmploymentRecord.ValueState.MISSING,
    }:
        return EmploymentRecord.DatePrecision.UNKNOWN
    return EmploymentRecord.DatePrecision.DAY


def _replace_skills(profile: CandidateProfile, skills: Iterable[str]) -> None:
    CandidateSkill.objects.filter(profile=profile).delete()
    CandidateSkill.objects.bulk_create(
        [
            CandidateSkill(
                profile=profile,
                normalized_name=" ".join(value.casefold().split()),
                display_name=value.strip(),
                ordering=index,
            )
            for index, value in enumerate(skills)
        ]
    )


def _replace_links(profile: CandidateProfile, links: Iterable[str]) -> None:
    ProfileLink.objects.filter(profile=profile).delete()
    ProfileLink.objects.bulk_create(
        [
            ProfileLink(profile=profile, normalized_url=value, ordering=index)
            for index, value in enumerate(links)
        ]
    )


def _replace_employment(
    profile: CandidateProfile, records: list[dict[str, object]]
) -> list[dict[str, object]]:
    existing = {str(item.id): item for item in profile.employment_history.all()}
    retained: set[str] = set()
    changes: list[dict[str, object]] = []
    for ordering, values in enumerate(records):
        record_id = values.pop("id", None)
        if record_id is not None:
            record = existing.get(str(record_id))
            if record is None:
                raise ValidationError({"employment_history": "Employment record is unavailable."})
            retained.add(str(record.id))
            prior_version = record.version
            for key, value in values.items():
                setattr(
                    record,
                    key,
                    value if value is not None else "" if key == "role_title" else value,
                )
            record.ordering = ordering
            record.start_date_precision = _date_precision(
                record.start_date, record.start_date_state
            )
            record.end_date_precision = _date_precision(record.end_date, record.end_date_state)
            record.version += 1
            record.full_clean()
            record.save()
            changes.append(
                {
                    "record_id": str(record.id),
                    "version": record.version,
                    "prior_version": prior_version,
                }
            )
        else:
            record = EmploymentRecord(
                profile=profile,
                ordering=ordering,
                start_date_precision=_date_precision(
                    values.get("start_date"), str(values["start_date_state"])
                ),
                end_date_precision=_date_precision(
                    values.get("end_date"), str(values["end_date_state"])
                ),
                **values,
            )
            if record.role_title is None:
                record.role_title = ""
            record.full_clean()
            record.save()
            retained.add(str(record.id))
            changes.append(
                {"record_id": str(record.id), "version": record.version, "prior_version": None}
            )
    for record_id, record in existing.items():
        if record_id not in retained:
            changes.append({"record_id": record_id, "version": record.version + 1, "deleted": True})
            record.delete()
    return changes


@transaction.atomic
def update_profile(
    *, identity, if_match: str | None, values: dict[str, object]
) -> CandidateProfile:
    profile = CandidateProfile.objects.select_for_update().get(identity=identity)
    attempted = dict(values)
    require_match(
        if_match,
        object_id=profile.id,
        version=profile.version,
        current=profile_data(profile),
        attempted=attempted,
    )
    employment_changes: list[dict[str, object]] = []
    if "full_name" in values:
        profile.full_name_ciphertext = encrypt(str(values.pop("full_name")))
    if "compensation" in values:
        compensation = values.pop("compensation")
        profile.compensation_ciphertext = (
            encrypt(safe_json(compensation)) if compensation is not None else None
        )
    if "skills" in values:
        _replace_skills(profile, cast(list[str], values.pop("skills")))
    if "professional_links" in values:
        _replace_links(profile, cast(list[str], values.pop("professional_links")))
    if "employment_history" in values:
        employment_changes = _replace_employment(
            profile, cast(list[dict[str, object]], values.pop("employment_history"))
        )
    for key, value in values.items():
        if hasattr(profile, key):
            setattr(
                profile,
                key,
                value
                if value is not None
                else ""
                if key
                in {
                    "headline",
                    "current_role",
                    "current_company",
                    "meaningful_work",
                    "notice_period",
                }
                else value,
            )
    profile.last_candidate_activity_at = timezone.now()
    profile.version += 1
    profile.full_clean()
    profile.save()
    if employment_changes:
        enqueue(
            aggregate_type="candidate_profile",
            aggregate_id=profile.id,
            aggregate_version=profile.version,
            event_type="profile.employment_history_changed.v1",
            payload={
                "candidate_profile_id": str(profile.id),
                "records": employment_changes,
                "changed_fields": ["employment_history"],
            },
            idempotency_key=f"employment-history:{profile.id}:{profile.version}",
            actor_id=identity.id,
        )
    record_audit_event(
        actor=identity,
        action="CANDIDATE_PROFILE_UPDATE",
        target_type="candidate_profile",
        target_id=str(profile.id),
        outcome="ALLOWED",
        metadata={"changed_fields": sorted(attempted), "version": profile.version},
    )
    return profile


@transaction.atomic
def publish_profile(*, identity, if_match: str | None) -> CandidateProfile:
    profile = CandidateProfile.objects.select_for_update().get(identity=identity)
    require_match(
        if_match,
        object_id=profile.id,
        version=profile.version,
        current=profile_data(profile),
        attempted={"profile_state": CandidateProfile.State.PUBLISHED},
    )
    missing = []
    if not profile.full_name_ciphertext:
        missing.append("full_name")
    if not profile.location:
        missing.append("location")
    if not profile.skills.exists():
        missing.append("skills")
    if not profile.resumes.filter(
        scan_status="CLEAN", parse_status="READY", is_current=True
    ).exists():
        missing.append("resume")
    visibility = current_visibility(profile)
    if visibility is None or visibility.consent_record.withdrawn_at is not None:
        missing.extend(["visibility", "consent"])
    if missing:
        raise ValidationError({field: "Required before publication." for field in missing})
    profile.profile_state = (
        CandidateProfile.State.HIDDEN
        if visibility.mode == "NOT_LOOKING"
        else CandidateProfile.State.PUBLISHED
    )
    profile.consent_expires_at = timezone.now() + timedelta(days=365)
    profile.version += 1
    profile.save(update_fields=("profile_state", "consent_expires_at", "version", "updated_at"))
    enqueue(
        aggregate_type="candidate_profile",
        aggregate_id=profile.id,
        aggregate_version=profile.version,
        event_type="profile.published.v1",
        payload={"candidate_profile_id": str(profile.id)},
        idempotency_key=f"profile-published:{profile.id}:{profile.version}",
        actor_id=identity.id,
    )
    return profile
