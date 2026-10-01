from __future__ import annotations

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from modules.recruiting.models import Application, CandidateWorkRecord
from modules.tenancy.audit import record_governance_event
from modules.tenancy.policy import AuthorizationRequest, authorize

from .models import SavedSearch, SearchDefinition


def _criteria(search: SearchDefinition) -> dict:
    return {
        "context": search.criteria_context,
        "groups": [
            {
                "id": str(group.stable_id),
                "purpose": group.purpose,
                "operator": group.operator,
                "label": group.label or None,
            }
            for group in search.groups.all()
        ],
        "criteria": [
            {
                "id": str(item.stable_id),
                "group_id": str(item.group.stable_id),
                "field": item.field,
                "operator": item.operator,
                "value": item.value,
            }
            for item in search.criteria.select_related("group").all()
        ],
        "limit": search.result_limit,
    }


def _status_snapshot(search: SearchDefinition) -> dict[str, str]:
    statuses = {
        str(item.candidate_profile_id): item.internal_status
        for item in CandidateWorkRecord.objects.filter(originating_search=search)
    }
    if search.derived_opening_id:
        statuses.update(
            {
                str(item.candidate_profile_id): item.internal_status
                for item in Application.objects.filter(opening_id=search.derived_opening_id)
            }
        )
    return statuses


def _snapshot(search: SearchDefinition) -> dict:
    opening = search.derived_opening
    return {
        "result_ids": [
            str(value) for value in search.results.values_list("candidate_profile_id", flat=True)
        ],
        "candidate_statuses": _status_snapshot(search),
        "opening_state": opening.state if opening else None,
        "opening_version": opening.version if opening else None,
    }


def _changes(item: SavedSearch) -> list[str]:
    current = _snapshot(item.search)
    saved = item.result_context_snapshot
    changes = []
    if current["opening_state"] != saved.get("opening_state"):
        changes.append("OPENING_STATE")
    elif current["opening_version"] != saved.get("opening_version"):
        changes.append("OPENING_CHANGED")
    if current["result_ids"] != saved.get("result_ids", []):
        changes.append("RESULT_SET")
    if current["candidate_statuses"] != saved.get("candidate_statuses", {}):
        changes.append("CANDIDATE_STATUS")
    return changes


def project_saved_search(item: SavedSearch) -> dict:
    return {
        "id": str(item.id),
        "name": item.name,
        "search_id": str(item.search_id),
        "prompt": item.search.prompt,
        "criteria": _criteria(item.search),
        "result_context": item.result_context_snapshot,
        "changed_since_save": _changes(item),
        "version": item.version,
    }


def _authorize(membership) -> None:
    authorize(
        AuthorizationRequest(
            action="saved_search.manage",
            role=membership.role,
            tenant_id=membership.tenant_id,
            object_tenant_id=membership.tenant_id,
            actor=membership.identity,
        )
    )


@transaction.atomic
def create_saved_search(*, membership, name: str, search_id) -> SavedSearch:
    _authorize(membership)
    search = (
        SearchDefinition.objects.select_related("derived_opening")
        .filter(pk=search_id, tenant_id=membership.tenant_id, actor=membership.identity)
        .first()
    )
    if search is None:
        raise PermissionDenied("Saved search unavailable")
    if not name.strip():
        raise ValidationError({"name": "Name is required."})
    item = SavedSearch(
        search=search,
        tenant_id=membership.tenant_id,
        actor=membership.identity,
        name=name.strip(),
        result_context_snapshot=_snapshot(search),
    )
    item.full_clean()
    item.save()
    record_governance_event(
        membership=membership,
        action="SAVED_SEARCH_CREATE",
        target_type="saved_search",
        target_id=item.id,
        changed_fields=["name", "search_id"],
    )
    return item


def list_saved_searches(*, membership):
    _authorize(membership)
    return SavedSearch.objects.filter(
        tenant_id=membership.tenant_id, actor=membership.identity
    ).select_related("search", "search__derived_opening")


def get_saved_search(*, membership, search_id) -> SavedSearch:
    _authorize(membership)
    item = (
        SavedSearch.objects.select_related("search", "search__derived_opening")
        .filter(
            search_id=search_id,
            tenant_id=membership.tenant_id,
            actor=membership.identity,
        )
        .first()
    )
    if item is None:
        raise PermissionDenied("Saved search unavailable")
    return item
