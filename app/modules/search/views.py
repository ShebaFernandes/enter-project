from __future__ import annotations

import base64
import binascii
from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view
from rest_framework.response import Response

from modules.operations.crypto import decrypt
from modules.tenancy.models import TenantMembership

from .audit import audit_result_view, audit_search, audit_search_denial
from .eligibility import consent_allows_findings, eligible_profiles, validate_search_context
from .engine import evaluate_candidate, validate_criteria
from .models import CriteriaGroup, Criterion, SavedSearch, SearchDefinition, SearchResultSnapshot
from .projections import authorized_findings
from .query import SearchTemporarilyUnavailable, search_authorization_context, with_query_timeout
from .serializers import SavedSearchInputSerializer, SearchCriteriaSerializer


def _membership(request, tenant_id):
    membership = getattr(request, "tenant_membership", None)
    if (
        membership is None
        or str(membership.tenant_id) != str(tenant_id)
        or membership.role
        not in {TenantMembership.Role.RECRUITER, TenantMembership.Role.HIRING_MANAGER}
    ):
        if getattr(request.user, "is_authenticated", False):
            audit_search_denial(
                actor=request.user,
                tenant_id=tenant_id,
                reason_code="MEMBERSHIP_OR_ROLE_UNAVAILABLE",
            )
        raise PermissionDenied("Search unavailable")
    return membership


def _candidate_values(profile):
    loc = (
        profile.location.get("normalized")
        or profile.location.get("display")
        or profile.location.get("city")
    )
    return {
        "skills": list(profile.skills.values_list("normalized_name", flat=True)),
        "location": loc,
        "experience_years": profile.experience_years,
        "work_arrangements": profile.work_arrangements,
        "availability_date": profile.availability_date,
        "role_categories": profile.role_categories,
    }


def _result(profile, matched, membership):
    try:
        name = (
            decrypt(bytes(profile.full_name_ciphertext))
            if profile.full_name_ciphertext
            else "Candidate"
        )
    except Exception:
        name = "Candidate"
    return {
        "candidate_id": str(profile.id),
        "summary": {
            "name": name,
            "headline": profile.headline,
            "current_role": profile.current_role,
            "current_company": profile.current_company,
            "location": profile.location,
            "experience_years": str(profile.experience_years),
            "skills": list(profile.skills.values_list("display_name", flat=True)),
            "work_arrangements": profile.work_arrangements,
            "availability_date": profile.availability_date,
        },
        "score": str(matched.score),
        "evidence": matched.evidence,
        "findings": authorized_findings(
            profile, allow=consent_allows_findings(profile, membership.tenant_id)
        ),
        "unknowns": matched.unknowns,
        "explanation": None,
    }


@api_view(["POST"])
@transaction.atomic
def execute_search(request, tenant_id):
    membership = _membership(request, tenant_id)
    serializer = SearchCriteriaSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    opening = validate_search_context(data["context"], membership)
    search = SearchDefinition(
        tenant_id=tenant_id,
        actor=request.user,
        prompt="",
        context_type=data["context"]["type"],
        criteria_context={
            "type": data["context"]["type"],
            **({"opening_id": str(opening.id)} if opening else {}),
        },
        derived_opening=opening,
        result_limit=data["limit"],
    )
    search.full_clean()
    search.save()
    stale_recent = list(
        SearchDefinition.objects.filter(
            tenant_id=tenant_id,
            actor=request.user,
            context_type=SearchDefinition.ContextType.AD_HOC,
            saved__isnull=True,
        )
        .order_by("-created_at")
        .values_list("id", flat=True)[6:]
    )
    if stale_recent:
        SearchDefinition.objects.filter(id__in=stale_recent).delete()
    groups = validate_criteria(data["groups"], data["criteria"])
    group_models = {
        str(group["id"]): CriteriaGroup.objects.create(
            stable_id=group["id"],
            search=search,
            purpose=group["purpose"],
            operator=group["operator"],
            label=group.get("label") or "",
        )
        for group in data["groups"]
    }
    for item in data["criteria"]:
        Criterion.objects.create(
            stable_id=item["id"],
            search=search,
            group=group_models[str(item["group_id"])],
            field=item["field"],
            operator=item["operator"],
            value=item["value"],
        )
    try:
        with search_authorization_context(data["context"]):
            profiles = with_query_timeout(
                lambda: list(
                    eligible_profiles(membership, data["context"]).prefetch_related(
                        "skills", "consents", "findings"
                    )
                )
            )
    except SearchTemporarilyUnavailable:
        return Response(
            {
                "title": "Search temporarily unavailable",
                "status": 503,
                "typed_search_available": True,
            },
            status=503,
        )
    ranked = []
    for profile in profiles:
        matched = evaluate_candidate(_candidate_values(profile), groups)
        if matched.eligible:
            ranked.append((profile, matched))
    ranked.sort(key=lambda pair: (-pair[1].score, str(pair[0].id)))
    try:
        offset = (
            int(base64.urlsafe_b64decode(data.get("cursor") or "MA==").decode())
            if data.get("cursor")
            else 0
        )
        if offset < 0:
            raise ValueError
    except (ValueError, UnicodeDecodeError, binascii.Error):
        return Response({"cursor": ["Cursor is invalid."]}, status=422)
    page = ranked[offset : offset + data["limit"]]
    items = []
    for ordinal, (profile, matched) in enumerate(page, offset + 1):
        item = _result(profile, matched, membership)
        items.append(item)
        SearchResultSnapshot.objects.create(
            search=search,
            candidate_profile_id=profile.id,
            ordinal=ordinal,
            score=Decimal(item["score"]),
            evidence=matched.evidence,
            unknowns=matched.unknowns,
        )
    next_cursor = (
        base64.urlsafe_b64encode(str(offset + len(page)).encode()).decode()
        if offset + len(page) < len(ranked)
        else None
    )
    audit_search(
        actor=request.user,
        tenant_id=tenant_id,
        search_id=search.id,
        outcome="ALLOWED",
        result_count=len(items),
    )
    return Response({"items": items, "next_cursor": next_cursor, "search_id": str(search.id)})


def _criteria(search):
    return {
        "context": search.criteria_context,
        "groups": [
            {
                "id": str(g.stable_id),
                "purpose": g.purpose,
                "operator": g.operator,
                "label": g.label or None,
            }
            for g in search.groups.all()
        ],
        "criteria": [
            {
                "id": str(c.stable_id),
                "group_id": str(c.group.stable_id),
                "field": c.field,
                "operator": c.operator,
                "value": c.value,
            }
            for c in search.criteria.all()
        ],
        "limit": search.result_limit,
    }


def _saved(item):
    return {
        "id": str(item.id),
        "name": item.name,
        "search_id": str(item.search_id),
        "prompt": item.search.prompt,
        "criteria": _criteria(item.search),
        "result_context": {"result_count": item.search.results.count()},
        "changed_since_save": [],
        "version": item.version,
    }


@api_view(["GET", "POST"])
def saved_searches(request, tenant_id):
    membership = _membership(request, tenant_id)
    if request.method == "GET":
        return Response(
            [
                _saved(item)
                for item in SavedSearch.objects.filter(
                    tenant_id=tenant_id, actor=request.user
                ).select_related("search")
            ]
        )
    serializer = SavedSearchInputSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    search = get_object_or_404(
        SearchDefinition,
        pk=serializer.validated_data["search_id"],
        tenant_id=tenant_id,
        actor=request.user,
    )
    item = SavedSearch.objects.create(
        search=search,
        tenant_id=membership.tenant_id,
        actor=request.user,
        name=serializer.validated_data["name"],
    )
    return Response(_saved(item), status=201)


@api_view(["GET"])
def reopen_search(request, tenant_id, search_id):
    _membership(request, tenant_id)
    item = get_object_or_404(
        SavedSearch.objects.select_related("search"),
        search_id=search_id,
        tenant_id=tenant_id,
        actor=request.user,
    )
    return Response(_saved(item))


@api_view(["GET"])
@transaction.atomic
def candidate_detail(request, tenant_id, candidate_id):
    membership = _membership(request, tenant_id)
    search_id = request.query_params.get("search_id")
    snapshot = get_object_or_404(
        SearchResultSnapshot.objects.select_related("search"),
        search_id=search_id,
        candidate_profile_id=candidate_id,
        search__tenant_id=tenant_id,
        search__actor=request.user,
    )
    with search_authorization_context(snapshot.search.criteria_context):
        profile = (
            eligible_profiles(membership, snapshot.search.criteria_context)
            .filter(pk=candidate_id)
            .prefetch_related("skills", "findings", "consents")
            .first()
        )
    if profile is None:
        audit_result_view(
            actor=request.user,
            tenant_id=tenant_id,
            search_id=search_id,
            candidate_id=candidate_id,
            outcome="DENIED",
        )
        raise PermissionDenied("Candidate unavailable")
    matched = evaluate_candidate(
        _candidate_values(profile),
        validate_criteria(
            _criteria(snapshot.search)["groups"], _criteria(snapshot.search)["criteria"]
        ),
    )
    audit_result_view(
        actor=request.user,
        tenant_id=tenant_id,
        search_id=search_id,
        candidate_id=candidate_id,
        outcome="ALLOWED",
    )
    result = _result(profile, matched, membership)
    return Response(
        {
            "candidate_id": result["candidate_id"],
            "permitted_fields": result["summary"],
            "evidence": result["evidence"],
            "findings": result["findings"],
            "unknowns": result["unknowns"],
            "access_context": snapshot.search.criteria_context,
        }
    )
