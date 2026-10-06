from __future__ import annotations

from typing import Any

from pydantic import ValidationError as PydanticValidationError
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.response import Response

from modules.ai.intent_schema import SearchCriteriaInput, SearchIntent
from modules.ai.search_graph import complete_checkpoint, interpret_search, persist_checkpoint

from .audit import audit_criteria_preview
from .eligibility import eligible_profiles, validate_search_context
from .engine import evaluate_candidate, validate_criteria
from .serializers import ContextSerializer, SearchCriteriaSerializer
from .views import _candidate_values, _membership, execute_search


def _json_criteria(criteria: SearchCriteriaInput) -> dict[str, Any]:
    return criteria.model_dump(mode="json", exclude_none=True)


def _estimate(membership, criteria: dict[str, Any]) -> int:
    validate_search_context(criteria["context"], membership)
    groups = validate_criteria(criteria["groups"], criteria["criteria"])
    profiles = eligible_profiles(membership, criteria["context"]).prefetch_related("skills")
    return sum(
        1 for profile in profiles if evaluate_candidate(_candidate_values(profile), groups).eligible
    )


def _group_impacts(membership, criteria: dict[str, Any]) -> list[dict[str, Any]]:
    impacts = []
    for group in criteria["groups"]:
        toggled = {
            **criteria,
            "groups": [
                {
                    **candidate,
                    "operator": ("ANY" if candidate["operator"] == "ALL" else "ALL"),
                }
                if candidate["id"] == group["id"]
                else candidate
                for candidate in criteria["groups"]
            ],
        }
        impacts.append(
            {
                "group_id": group["id"],
                "operator": group["operator"],
                "estimated_count": _estimate(membership, criteria),
                "alternate_operator": "ANY" if group["operator"] == "ALL" else "ALL",
                "alternate_estimated_count": _estimate(membership, toggled),
            }
        )
    return impacts


@api_view(["POST"])
def interpret_search_view(request, tenant_id):
    membership = _membership(request, tenant_id)
    prompt = request.data.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 4000:
        raise serializers.ValidationError({"prompt": "Enter between 1 and 4000 characters."})
    context_serializer = ContextSerializer(data=request.data.get("context"))
    context_serializer.is_valid(raise_exception=True)
    context = {
        key: str(value) if key == "opening_id" else value
        for key, value in context_serializer.validated_data.items()
    }
    validate_search_context(context, membership)

    submitted = request.data.get("criteria")
    workflow_id = request.data.get("workflow_id")
    if submitted is None:
        intent = interpret_search(prompt.strip(), context)
    else:
        serializer = SearchCriteriaSerializer(data=submitted)
        serializer.is_valid(raise_exception=True)
        if submitted.get("context") != request.data.get("context"):
            raise serializers.ValidationError(
                {"criteria.context": "Reviewed criteria must retain the submitted search context."}
            )
        try:
            criteria_model = SearchCriteriaInput.model_validate(submitted)
        except PydanticValidationError as exc:
            raise serializers.ValidationError({"criteria": str(exc)}) from exc
        intent = SearchIntent(
            criteria=criteria_model,
            requires_review=False,
            ambiguities=[],
            ai_status="NOT_NEEDED",
        )

    criteria = _json_criteria(intent.criteria)
    estimated_count = _estimate(membership, criteria)
    if submitted is not None and workflow_id:
        workflow = complete_checkpoint(
            str(workflow_id), intent, actor=request.user, tenant_id=tenant_id
        )
    else:
        workflow = persist_checkpoint(
            intent, actor=request.user, tenant_id=tenant_id, prompt=prompt.strip()
        )
    payload = {
        "original_prompt": prompt.strip(),
        "criteria": criteria,
        "requires_review": intent.requires_review,
        "ambiguities": intent.ambiguities,
        "clarifications": [item.model_dump(mode="json") for item in intent.clarifications],
        "ai_status": intent.ai_status,
        "estimated_count": estimated_count,
        "group_impacts": _group_impacts(membership, criteria),
        "workflow_id": str(workflow.id),
    }
    audit_criteria_preview(
        actor=request.user,
        tenant_id=tenant_id,
        prompt=prompt.strip(),
        ai_status=intent.ai_status,
        result_count=estimated_count,
    )
    return Response(payload)


# The approved contract uses the same POST /searches operation for manual and
# recruiter-confirmed criteria. Re-exporting the existing view keeps one execution
# implementation and prevents the AI review layer from acquiring search authority.
execute_reviewed_search = execute_search
