from __future__ import annotations

import uuid

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.db.models import Q, QuerySet
from django.utils import timezone

from modules.candidate.models import CandidateProfile, VisibilityRule
from modules.recruiting.models import Opening
from modules.tenancy.models import TenantMembership
from modules.tenancy.policy import AuthorizationRequest, authorize, authorize_opening


def validate_search_context(context: dict, membership: TenantMembership) -> Opening | None:
    if set(context) - {"type", "opening_id"}:
        raise ValidationError("Search context contains unsupported fields.")
    kind = context.get("type")
    if kind == "AD_HOC":
        if "opening_id" in context:
            raise ValidationError("AD_HOC must not contain opening_id.")
        return None
    if kind != "OPENING" or not context.get("opening_id"):
        raise ValidationError("OPENING requires exactly one opening_id.")
    try:
        opening_id = uuid.UUID(str(context["opening_id"]))
    except ValueError as exc:
        raise ValidationError("opening_id is invalid.") from exc
    opening = Opening.objects.filter(pk=opening_id, tenant_id=membership.tenant_id).first()
    if opening is None or opening.state != Opening.State.OPEN:
        raise PermissionDenied("Search context unavailable")
    authorize_opening(membership, opening, "opening.read")
    return opening


def _normalized(values):
    return {str(v).strip().casefold() for v in values if str(v).strip()}


def _json_array_has(field: str, value: str) -> Q:
    if connection.vendor == "postgresql":
        return Q(**{f"{field}__contains": [value]})
    query = Q()
    for index in range(20):
        query |= Q(**{f"{field}__{index}": value})
    return query


def preference_matches(profile: CandidateProfile, opening: Opening) -> bool:
    rule = profile.visibility_rules.filter(superseded_at__isnull=True).first()
    if rule is None or rule.mode != VisibilityRule.Mode.MATCHING_ROLES:
        return False
    prefs = rule.matching_preferences
    roles = _normalized(prefs.get("role_categories", profile.role_categories))
    locations = _normalized(prefs.get("preferred_locations", profile.preferred_locations))
    arrangements = _normalized(prefs.get("work_arrangements", profile.work_arrangements))
    opening_location = (
        opening.location.get("normalized")
        or opening.location.get("display")
        or opening.location.get("city")
        or ""
    )
    return bool(
        roles
        and locations
        and arrangements
        and opening.title.casefold() in roles
        and str(opening_location).casefold() in locations
        and opening.work_mode.casefold() in arrangements
    )


def eligible_profiles(membership: TenantMembership, context: dict) -> QuerySet[CandidateProfile]:
    authorize(
        AuthorizationRequest(
            action="candidate.search",
            role=membership.role,
            tenant_id=membership.tenant_id,
            object_tenant_id=membership.tenant_id,
            actor=membership.identity,
        )
    )
    opening = validate_search_context(context, membership)
    now = timezone.now()
    base = CandidateProfile.objects.filter(
        profile_state=CandidateProfile.State.PUBLISHED,
        consents__purpose="RECRUITING_DISCOVERY",
        consents__withdrawn_at__isnull=True,
        consents__expires_at__gt=now,
        visibility_rules__superseded_at__isnull=True,
    )
    base = base.filter(_json_array_has("consents__field_scope", "profile"))
    if opening is None:
        return (
            base.filter(
                visibility_rules__mode=VisibilityRule.Mode.APPROVED_RECRUITERS,
            )
            .filter(
                _json_array_has("visibility_rules__approved_tenant_ids", str(membership.tenant_id))
            )
            .filter(
                _json_array_has(
                    "consents__audience_scope__approved_tenant_ids",
                    str(membership.tenant_id),
                )
            )
            .distinct()
        )
    opening_location = (
        opening.location.get("normalized")
        or opening.location.get("display")
        or opening.location.get("city")
        or ""
    )
    return (
        base.filter(visibility_rules__mode=VisibilityRule.Mode.MATCHING_ROLES)
        .filter(
            _json_array_has(
                "visibility_rules__matching_preferences__role_categories",
                opening.title.casefold(),
            ),
            _json_array_has(
                "visibility_rules__matching_preferences__preferred_locations",
                str(opening_location).casefold(),
            ),
            _json_array_has(
                "visibility_rules__matching_preferences__work_arrangements",
                opening.work_mode,
            ),
        )
        .distinct()
    )


def consent_allows_findings(profile: CandidateProfile, tenant_id) -> bool:
    now = timezone.now()
    base = profile.consents.filter(
        purpose="RECRUITING_DISCOVERY",
        withdrawn_at__isnull=True,
        expires_at__gt=now,
    )
    base = base.filter(_json_array_has("field_scope", "employment_history"))
    return base.filter(
        _json_array_has("audience_scope__approved_tenant_ids", str(tenant_id))
        | Q(profile__visibility_rules__mode="MATCHING_ROLES")
    ).exists()
