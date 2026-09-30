from __future__ import annotations

import hashlib
import os
from datetime import timedelta
from typing import Any, Protocol, TypedDict, cast

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone
from langgraph.graph import END, START, StateGraph
from pydantic import ValidationError

from modules.operations.crypto import encrypt, safe_json
from modules.operations.models import WorkflowRun

from .bedrock import BedrockSearchIntentGateway, BedrockUnavailable, ModelResponse
from .intent_schema import PROTECTED_TERMS, SearchIntent, deterministic_fallback


class GraphState(TypedDict, total=False):
    prompt: str
    context: dict[str, object]
    parsed: SearchIntent
    invalid_output: bool


class SearchIntentGateway(Protocol):
    def interpret(
        self, prompt: str, context: dict[str, object], *, repair: bool = False
    ) -> ModelResponse: ...


def _safe_fallback(prompt: str, context: dict[str, object], status: str) -> SearchIntent:
    fallback = deterministic_fallback(prompt, context)
    return fallback.model_copy(
        update={
            "ai_status": status,
            "requires_review": True,
            "ambiguities": [
                *fallback.ambiguities,
                "Model interpretation was unavailable or invalid; verify all criteria manually.",
            ],
        }
    )


def interpret_search(
    prompt: str,
    context: dict[str, object],
    *,
    gateway: SearchIntentGateway | None = None,
) -> SearchIntent:
    model_gateway = gateway or BedrockSearchIntentGateway()

    def parse(state: GraphState) -> GraphState:
        try:
            response = model_gateway.interpret(state["prompt"], state["context"])
        except BedrockUnavailable:
            return {"parsed": _safe_fallback(state["prompt"], state["context"], "UNAVAILABLE")}
        for repair in (False, True):
            try:
                parsed = SearchIntent.model_validate_json(response.text)
                if parsed.criteria.context.model_dump(mode="json") != state["context"]:
                    raise ValueError("Model changed the authoritative search context")
                ambiguities = list(parsed.ambiguities)
                if len(parsed.criteria.criteria) < 2:
                    ambiguities.append(
                        "The interpretation is materially incomplete; review the visible criteria."
                    )
                if any(term in state["prompt"].casefold() for term in PROTECTED_TERMS):
                    ambiguities.append(
                        "Protected-attribute language requires review and cannot become "
                        "a criterion."
                    )
                parsed = parsed.model_copy(
                    update={
                        "ai_status": "USED",
                        "ambiguities": list(dict.fromkeys(ambiguities)),
                        "requires_review": parsed.requires_review or bool(ambiguities),
                    }
                )
                return {"parsed": parsed}
            except (ValidationError, ValueError):
                if repair:
                    break
                try:
                    response = model_gateway.interpret(
                        state["prompt"], state["context"], repair=True
                    )
                except BedrockUnavailable:
                    break
        return {"parsed": _safe_fallback(state["prompt"], state["context"], "INVALID_OUTPUT")}

    graph = StateGraph(GraphState)
    graph.add_node("parse", parse)
    graph.add_edge(START, "parse")
    graph.add_edge("parse", END)
    compiled = graph.compile()
    initial_state: GraphState = {"prompt": prompt, "context": context}
    # LangGraph's compiled generic loses the concrete TypedDict at this boundary.
    result = cast(Any, compiled).invoke(initial_state)
    return result["parsed"]


def minimized_checkpoint(
    intent: SearchIntent, *, actor_id: str, tenant_id: str
) -> dict[str, object]:
    """Return only resumable identifiers/hashes; raw prompts and candidate data are excluded."""
    criteria = intent.criteria
    return {
        "schema_version": intent.schema_version,
        "actor_id": actor_id,
        "tenant_id": tenant_id,
        "group_ids": [str(group.id) for group in criteria.groups],
        "criterion_ids": [str(item.id) for item in criteria.criteria],
        "criteria_hash": hashlib.sha256(
            criteria.model_dump_json(exclude={"cursor"}).encode()
        ).hexdigest(),
        "requires_review": intent.requires_review,
    }


def persist_checkpoint(intent: SearchIntent, *, actor, tenant_id, prompt: str) -> WorkflowRun:
    checkpoint = minimized_checkpoint(intent, actor_id=str(actor.id), tenant_id=str(tenant_id))
    status = (
        WorkflowRun.Status.AWAITING_REVIEW
        if intent.requires_review
        else WorkflowRun.Status.COMPLETED
    )
    expiry_days = 30 if intent.requires_review else 7
    return WorkflowRun.objects.create(
        workflow_type="SEARCH_INTERPRETATION",
        actor=actor,
        tenant_id=tenant_id,
        status=status,
        current_step="RECRUITER_REVIEW" if intent.requires_review else "VALIDATED_COMMIT",
        input_hash=hashlib.sha256(prompt.encode()).hexdigest(),
        model_version=os.getenv("BEDROCK_SEARCH_MODEL_ID", ""),
        prompt_version=intent.schema_version,
        checkpoint_ciphertext=encrypt(safe_json(checkpoint)),
        expires_at=timezone.now() + timedelta(days=expiry_days),
        last_error_category=(
            intent.ai_status if intent.ai_status in {"UNAVAILABLE", "INVALID_OUTPUT"} else ""
        ),
    )


@transaction.atomic
def complete_checkpoint(workflow_id: str, intent: SearchIntent, *, actor, tenant_id) -> WorkflowRun:
    workflow = (
        WorkflowRun.objects.select_for_update()
        .filter(
            pk=workflow_id,
            workflow_type="SEARCH_INTERPRETATION",
            actor=actor,
            tenant_id=tenant_id,
            status=WorkflowRun.Status.AWAITING_REVIEW,
            expires_at__gt=timezone.now(),
        )
        .first()
    )
    if workflow is None:
        raise PermissionDenied("Search review unavailable")
    checkpoint = minimized_checkpoint(intent, actor_id=str(actor.id), tenant_id=str(tenant_id))
    workflow.status = WorkflowRun.Status.COMPLETED
    workflow.current_step = "VALIDATED_COMMIT"
    workflow.checkpoint_ciphertext = encrypt(safe_json(checkpoint))
    workflow.expires_at = timezone.now() + timedelta(days=7)
    workflow.last_error_category = ""
    workflow.save(
        update_fields=(
            "status",
            "current_step",
            "checkpoint_ciphertext",
            "expires_at",
            "last_error_category",
            "updated_at",
        )
    )
    return workflow
