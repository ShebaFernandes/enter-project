from __future__ import annotations

import base64
import binascii
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view
from rest_framework.exceptions import APIException
from rest_framework.response import Response

from modules.operations.concurrency import strong_etag
from modules.operations.crypto import decrypt
from modules.recruiting.models import Application
from modules.tenancy.models import TenantMembership

from .audit import audit_result_view, audit_search, audit_search_denial
from .eligibility import (
    consent_allows_field,
    consent_allows_findings,
    eligible_profiles,
    validate_search_context,
)
from .engine import evaluate_candidate, validate_criteria
from .models import CriteriaGroup, Criterion, SavedSearch, SearchDefinition, SearchResultSnapshot
from .projections import authorized_findings
from .query import SearchTemporarilyUnavailable, search_authorization_context, with_query_timeout
from .recent import maintain_recent_searches
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


def _candidate_values(profile, membership=None):
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
        "notice_period": profile.notice_period or None,
        "resume_keyword": [
            profile.current_role,
            profile.current_company,
            profile.headline,
            profile.meaningful_work,
            *list(profile.skills.values_list("normalized_name", flat=True)),
        ]
        + (
            list(
                profile.resumes.filter(
                    is_current=True,
                    deleted_at__isnull=True,
                    scan_status="CLEAN",
                    parse_status="READY",
                    facts__fact_type="resume_text",
                ).values_list("facts__normalized_value", flat=True)
            )
            if membership and consent_allows_field(profile, membership.tenant_id, "resume")
            else []
        ),
    }


def _result(profile, matched, membership, search_id=None):
    try:
        name = (
            decrypt(bytes(profile.full_name_ciphertext))
            if profile.full_name_ciphertext
            else "Candidate"
        )
    except Exception:
        name = "Candidate"
    history_allowed = consent_allows_findings(profile, membership.tenant_id)
    work = (
        profile.recruiter_work.filter(
            tenant_id=membership.tenant_id, originating_search_id=search_id
        ).first()
        if search_id
        else None
    )
    return {
        "candidate_id": str(profile.id),
        "summary": {
            "name": name,
            "internal_status": work.internal_status if work else "SOURCED",
            "headline": profile.headline,
            "meaningful_work": profile.meaningful_work,
            "current_role": profile.current_role,
            "current_company": profile.current_company,
            "location": profile.location,
            "experience_years": str(profile.experience_years),
            "skills": list(profile.skills.values_list("display_name", flat=True)),
            "work_arrangements": profile.work_arrangements,
            "availability_date": profile.availability_date,
            "notice_period": profile.notice_period,
            "employment_history": [
                {
                    "company": record.company,
                    "role_title": record.role_title,
                    "start_date": record.start_date
                    if record.start_date_state == "CONFIRMED"
                    else None,
                    "end_date": record.end_date if record.end_date_state == "CONFIRMED" else None,
                    "is_current": record.is_current,
                    "employment_type": record.employment_type,
                    "provenance": record.provenance,
                }
                for record in profile.employment_history.all()
            ]
            if history_allowed
            else [],
        },
        "score": str(matched.score),
        "evidence": matched.evidence,
        "findings": authorized_findings(profile, allow=history_allowed),
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
    maintain_recent_searches(membership=membership)
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
        matched = evaluate_candidate(_candidate_values(profile, membership), groups)
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
    # Persist ordered references once so later page reads do not re-execute search.
    for ordinal, (profile, matched) in enumerate(ranked, 1):
        if offset < ordinal <= offset + data["limit"]:
            items.append(_result(profile, matched, membership, search.id))
        SearchResultSnapshot.objects.create(
            search=search,
            candidate_profile_id=profile.id,
            ordinal=ordinal,
            score=Decimal(matched.score),
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
    from modules.recruiting.candidate_work import create_or_reuse_candidate_work

    candidate_work, _ = create_or_reuse_candidate_work(
        membership=membership,
        candidate_id=profile.id,
        originating_search_id=snapshot.search_id,
        opening_id=snapshot.search.derived_opening_id,
        trigger="VIEW",
    )
    matched = evaluate_candidate(
        _candidate_values(profile, membership),
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
    result = _result(profile, matched, membership, snapshot.search_id)
    application = None
    if snapshot.search.derived_opening_id:
        application = Application.objects.filter(
            tenant_id=tenant_id,
            opening_id=snapshot.search.derived_opening_id,
            candidate_profile_id=profile.id,
        ).first()
    resume = (
        profile.resumes.filter(
            is_current=True, deleted_at__isnull=True, scan_status="CLEAN", parse_status="READY"
        ).first()
        if consent_allows_field(profile, tenant_id, "resume")
        else None
    )
    if request.query_params.get("download") == "resume":
        if resume is None or not resume.clean_key:
            raise PermissionDenied("Resume unavailable")
        from modules.candidate.resume_processing import storage_client

        try:
            stored = storage_client().get_object(
                Bucket=settings.RESUME_QUARANTINE_BUCKET, Key=resume.clean_key
            )
        except Exception as exc:
            raise APIException("Resume download is temporarily unavailable.") from exc
        extension = {"application/pdf": "pdf", "application/msword": "doc"}.get(
            resume.detected_mime, "docx"
        )
        response = FileResponse(
            stored["Body"],
            as_attachment=True,
            filename=f"resume.{extension}",
            content_type=resume.detected_mime,
        )
        response["Cache-Control"] = "no-store, private"
        return response
    return Response(
        {
            "resume_download_available": bool(resume and resume.clean_key),
            "candidate_id": result["candidate_id"],
            "permitted_fields": result["summary"],
            "evidence": result["evidence"],
            "findings": result["findings"],
            "unknowns": result["unknowns"],
            "access_context": snapshot.search.criteria_context,
            "candidate_work": {
                "id": str(candidate_work.id),
                "version": candidate_work.version,
                "etag": strong_etag(candidate_work.id, candidate_work.version),
                "internal_status": candidate_work.internal_status,
                "shortlisted": candidate_work.shortlisted,
            },
            "application_context": (
                {
                    "id": str(application.id),
                    "version": application.version,
                    "etag": strong_etag(application.id, application.version),
                    "internal_status": application.internal_status,
                    "candidate_status": application.candidate_status,
                }
                if application is not None
                else None
            ),
        }
    )
