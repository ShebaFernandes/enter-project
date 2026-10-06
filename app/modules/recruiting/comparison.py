from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.utils import timezone

from modules.candidate.models import CandidateProfile, VisibilityRule
from modules.operations.crypto import decrypt
from modules.search.eligibility import consent_allows_findings, eligible_profiles
from modules.search.models import SearchDefinition, SearchResultSnapshot
from modules.search.projections import authorized_findings
from modules.tenancy.policy import AuthorizationRequest, authorize, authorize_opening

from .models import Opening, ShortlistEntry

COMPARISON_FIELDS = [
    "name",
    "current_role",
    "current_company",
    "location",
    "experience",
    "notice_or_availability",
    "compensation_availability",
    "skills",
    "employment",
    "education",
    "preferences",
    "match_evidence",
    "informational_findings",
]

MATCH_EVIDENCE_SCOPES = {
    "skill": "skills",
    "experience_years": "profile",
    "location": "profile",
    "work_arrangement": "profile",
    "availability_date": "profile",
    "role_category": "profile",
}


@dataclass(frozen=True)
class ComparisonContext:
    context_type: str
    context_id: object
    eligibility_context: dict[str, str]
    snapshots: dict[str, SearchResultSnapshot]


def _authorize_comparison(membership) -> None:
    authorize(
        AuthorizationRequest(
            action="candidate.compare",
            role=membership.role,
            tenant_id=membership.tenant_id,
            object_tenant_id=membership.tenant_id,
            actor=membership.identity,
        )
    )


def _snapshot_map(queryset: Iterable[SearchResultSnapshot]) -> dict[str, SearchResultSnapshot]:
    snapshots: dict[str, SearchResultSnapshot] = {}
    for snapshot in queryset:
        snapshots.setdefault(str(snapshot.candidate_profile_id), snapshot)
    return snapshots


def _opening_context(*, membership, opening_id, shortlisted_only: bool) -> ComparisonContext:
    opening = (
        Opening.objects.select_related("business_unit")
        .filter(pk=opening_id, tenant_id=membership.tenant_id, state=Opening.State.OPEN)
        .first()
    )
    if opening is None:
        raise PermissionDenied("Comparison unavailable")
    authorize_opening(membership, opening, "opening.read")
    searches = SearchDefinition.objects.filter(
        tenant_id=membership.tenant_id,
        actor=membership.identity,
        context_type=SearchDefinition.ContextType.OPENING,
        derived_opening=opening,
    )
    snapshots = _snapshot_map(
        SearchResultSnapshot.objects.filter(search__in=searches)
        .select_related("search")
        .order_by("-search__created_at", "ordinal", "id")
    )
    if shortlisted_only:
        selected_ids: set[str] = set()
        entries = ShortlistEntry.objects.filter(
            tenant_id=membership.tenant_id, selected=True
        ).filter(Q(application__opening=opening) | Q(candidate_work__opening=opening))
        for entry in entries.select_related("application", "candidate_work"):
            if entry.application_id and entry.application is not None:
                candidate_id = entry.application.candidate_profile_id
            elif entry.candidate_work is not None:
                candidate_id = entry.candidate_work.candidate_profile_id
            else:
                continue
            selected_ids.add(str(candidate_id))
        snapshots = {key: value for key, value in snapshots.items() if key in selected_ids}
    return ComparisonContext(
        context_type="SHORTLIST" if shortlisted_only else "OPENING",
        context_id=opening.id,
        eligibility_context={"type": "OPENING", "opening_id": str(opening.id)},
        snapshots=snapshots,
    )


def _resolve_context(*, membership, context_type: str, context_id) -> ComparisonContext:
    _authorize_comparison(membership)
    if context_type == "SEARCH":
        search = (
            SearchDefinition.objects.select_related("derived_opening")
            .filter(
                pk=context_id,
                tenant_id=membership.tenant_id,
                actor=membership.identity,
            )
            .first()
        )
        if search is None:
            raise PermissionDenied("Comparison unavailable")
        if search.derived_opening_id:
            authorize_opening(membership, search.derived_opening, "opening.read")
        return ComparisonContext(
            context_type="SEARCH",
            context_id=search.id,
            eligibility_context=search.criteria_context,
            snapshots=_snapshot_map(search.results.order_by("ordinal", "id")),
        )
    if context_type == "OPENING":
        return _opening_context(
            membership=membership, opening_id=context_id, shortlisted_only=False
        )
    if context_type == "SHORTLIST":
        return _opening_context(membership=membership, opening_id=context_id, shortlisted_only=True)
    raise ValidationError({"context_type": "Unsupported comparison context."})


def _current_field_scope(profile: CandidateProfile, tenant_id: object) -> set[str]:
    now = timezone.now()
    rule = next(
        (item for item in profile.visibility_rules.all() if item.superseded_at is None),
        None,
    )
    if rule is None:
        return set()
    consent = rule.consent_record
    if (
        consent.purpose != "RECRUITING_DISCOVERY"
        or consent.withdrawn_at is not None
        or consent.expires_at <= now
    ):
        return set()
    if rule.mode == VisibilityRule.Mode.APPROVED_RECRUITERS:
        approved = {str(value) for value in consent.audience_scope.get("approved_tenant_ids", [])}
        if str(tenant_id) not in approved:
            return set()
    return {str(value) for value in consent.field_scope}


def _field(state: str, value: Any = None, provenance: Iterable[str] = ()) -> dict[str, Any]:
    return {
        "state": state,
        "value": value,
        "provenance": list(dict.fromkeys(provenance)),
    }


def _display_name(profile: CandidateProfile) -> str | None:
    if not profile.full_name_ciphertext:
        return None
    try:
        return decrypt(bytes(profile.full_name_ciphertext))
    except Exception:
        return None


def _location(profile: CandidateProfile) -> str | None:
    return (
        profile.location.get("display")
        or profile.location.get("normalized")
        or profile.location.get("city")
    )


def _employment_value(record) -> dict[str, Any]:
    return {
        "evidence_id": str(record.id),
        "company": record.company,
        "role_title": record.role_title or None,
        "start_date": record.start_date.isoformat() if record.start_date else None,
        "start_date_state": record.start_date_state,
        "end_date": record.end_date.isoformat() if record.end_date else None,
        "end_date_state": record.end_date_state,
        "is_current": record.is_current,
        "employment_type": record.employment_type,
        "employment_type_state": record.employment_type_state,
        "provenance": record.provenance,
    }


def _project_candidate(
    *,
    membership,
    profile: CandidateProfile,
    snapshot: SearchResultSnapshot,
    context: ComparisonContext,
) -> dict[str, Any]:
    scope = _current_field_scope(profile, membership.tenant_id)
    profile_allowed = "profile" in scope
    evidence: list[dict[str, Any]] = []

    name = _display_name(profile) if profile_allowed else None
    location = _location(profile) if profile_allowed else None
    notice_or_availability = None
    if profile_allowed:
        notice_or_availability = profile.notice_period or (
            profile.availability_date.isoformat() if profile.availability_date else None
        )

    if "skills" in scope:
        skills = list(profile.skills.all())
        skill_values = [skill.display_name for skill in skills]
        for skill in skills:
            evidence.append(
                {
                    "evidence_id": str(skill.id),
                    "category": "skills",
                    "label": skill.display_name,
                    "provenance": skill.provenance,
                }
            )
        skill_field = _field(
            "KNOWN" if skill_values else "UNKNOWN",
            skill_values or None,
            [skill.provenance for skill in skills],
        )
    else:
        skill_field = _field("UNAVAILABLE")

    if "employment_history" in scope:
        records = list(profile.employment_history.all())
        employment_values = [_employment_value(record) for record in records]
        complete_records = [
            record
            for record in records
            if record.start_date_state == "CONFIRMED"
            and (record.is_current or record.end_date_state == "CONFIRMED")
        ]
        for record in records:
            evidence.append(
                {
                    "evidence_id": str(record.id),
                    "category": "employment",
                    "label": record.company,
                    "provenance": record.provenance,
                }
            )
        employment_field = _field(
            "KNOWN" if complete_records else "UNKNOWN",
            employment_values or None,
            [record.provenance for record in records],
        )
    else:
        employment_field = _field("UNAVAILABLE")

    preferences = []
    if profile_allowed:
        preferences.extend(profile.role_categories)
        preferences.extend(profile.preferred_locations)
        preferences.extend(profile.work_arrangements)
    match_evidence = [
        dict(item)
        for item in snapshot.evidence
        if MATCH_EVIDENCE_SCOPES.get(str(item.get("label"))) in scope
    ]
    evidence.extend({**item, "category": "match_evidence"} for item in match_evidence)
    findings = authorized_findings(
        profile,
        allow=(
            "employment_history" in scope and consent_allows_findings(profile, membership.tenant_id)
        ),
    )
    fields = {
        "name": _field("KNOWN" if name else "UNKNOWN", name, ["CANDIDATE_REPORTED"]),
        "current_role": _field(
            "KNOWN" if profile.current_role else ("UNKNOWN" if profile_allowed else "UNAVAILABLE"),
            (profile.current_role or None) if profile_allowed else None,
            ["CANDIDATE_REPORTED"] if profile_allowed and profile.current_role else [],
        ),
        "current_company": _field(
            "KNOWN"
            if profile.current_company
            else ("UNKNOWN" if profile_allowed else "UNAVAILABLE"),
            (profile.current_company or None) if profile_allowed else None,
            ["CANDIDATE_REPORTED"] if profile_allowed and profile.current_company else [],
        ),
        "location": _field("KNOWN" if location else "UNKNOWN", location, ["CANDIDATE_REPORTED"]),
        "experience": _field(
            "KNOWN" if profile_allowed else "UNAVAILABLE",
            f"{profile.experience_years} years" if profile_allowed else None,
            ["CANDIDATE_REPORTED"] if profile_allowed else [],
        ),
        "notice_or_availability": _field(
            "KNOWN"
            if notice_or_availability
            else ("UNKNOWN" if profile_allowed else "UNAVAILABLE"),
            notice_or_availability,
            ["CANDIDATE_REPORTED"] if notice_or_availability else [],
        ),
        "compensation_availability": (
            _field(
                "KNOWN" if profile.compensation_ciphertext else "UNKNOWN",
                "Provided" if profile.compensation_ciphertext else None,
                ["CANDIDATE_REPORTED"] if profile.compensation_ciphertext else [],
            )
            if "compensation" in scope
            else _field("UNAVAILABLE")
        ),
        "skills": skill_field,
        "employment": employment_field,
        "education": _field(
            "KNOWN" if profile.education else ("UNKNOWN" if profile_allowed else "UNAVAILABLE"),
            (profile.education or None) if profile_allowed else None,
            ["CANDIDATE_REPORTED"] if profile_allowed and profile.education else [],
        ),
        "preferences": _field(
            "KNOWN" if preferences else ("UNKNOWN" if profile_allowed else "UNAVAILABLE"),
            preferences or None,
            ["CANDIDATE_REPORTED"] if preferences else [],
        ),
        "match_evidence": _field(
            "KNOWN" if match_evidence else "UNKNOWN",
            match_evidence or None,
            [str(item.get("provenance", "")) for item in match_evidence if item.get("provenance")],
        ),
        "informational_findings": _field(
            "KNOWN",
            [finding["code"] for finding in findings],
            ["DETERMINISTIC_EVALUATION"] if findings else [],
        ),
    }
    return {
        "candidate_id": str(profile.id),
        "permitted_fields": fields,
        "evidence": evidence,
        "findings": findings,
        "unknowns": [name for name in COMPARISON_FIELDS if fields[name]["state"] == "UNKNOWN"],
        "access_context": {
            "type": context.context_type,
            "id": str(context.context_id),
        },
    }


def compare_candidates(*, membership, candidate_ids, context_type: str, context_id) -> dict:
    ordered_ids = [str(value) for value in candidate_ids]
    if not 2 <= len(ordered_ids) <= 10 or len(set(ordered_ids)) != len(ordered_ids):
        raise ValidationError({"candidate_ids": "Select between two and ten unique candidates."})
    context = _resolve_context(
        membership=membership, context_type=context_type, context_id=context_id
    )
    selected = [candidate_id for candidate_id in ordered_ids if candidate_id in context.snapshots]
    current_profiles = {
        str(profile.id): profile
        for profile in eligible_profiles(membership, context.eligibility_context)
        .filter(id__in=selected)
        .prefetch_related(
            "skills",
            "employment_history",
            "findings",
            "consents",
            "visibility_rules__consent_record",
        )
    }
    candidates = [
        _project_candidate(
            membership=membership,
            profile=current_profiles[candidate_id],
            snapshot=context.snapshots[candidate_id],
            context=context,
        )
        for candidate_id in ordered_ids
        if candidate_id in current_profiles and candidate_id in context.snapshots
    ]
    from .audit import record_recruiting_event

    record_recruiting_event(
        actor=membership.identity,
        tenant_id=membership.tenant_id,
        action="CANDIDATE_COMPARISON_VIEWED",
        target_type="comparison_context",
        target_id=context.context_id,
        outcome="ALLOWED",
        selected_count=len(ordered_ids),
        returned_count=len(candidates),
        field_names=COMPARISON_FIELDS,
    )
    return {"fields": COMPARISON_FIELDS, "candidates": candidates}
