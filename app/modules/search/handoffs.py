"""Short-lived typed FM4 transport. No prompts, result copies or bearer-token storage."""

import hashlib
import json
import re
import secrets
from datetime import timedelta
from typing import Any

from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.http import Http404
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from rest_framework.exceptions import ValidationError

from modules.ai.intent_schema import SearchCriteriaInput
from modules.identity.services import current_session_credential
from modules.operations.concurrency import canonical_hash, require_if_match, strong_etag
from modules.operations.crypto import CryptoError, decrypt, encrypt
from modules.operations.models import WorkflowRun
from modules.tenancy.audit import record_governance_event
from modules.tenancy.models import TenantMembership

from .eligibility import validate_search_context
from .models import SearchDefinition, SearchWorkflowHandoff
from .saved_searches import _criteria


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def criteria_identity(value):
    """Compare stable-ID criteria independent of database retrieval order."""
    normalized = SearchCriteriaInput.model_validate(value).model_dump(
        mode="json", exclude_none=True
    )
    for field in ("groups", "criteria"):
        normalized[field] = sorted(normalized[field], key=lambda item: item["id"])
    return canonical_hash(normalized)


def authority(request, tenant_id):
    try:
        credential = current_session_credential(request)
        if not constant_time_compare(
            bytes(credential.session_key_hash),
            hashlib.sha256(request.session.session_key.encode()).digest(),
        ):
            raise Http404
    except (PermissionDenied, AttributeError):
        raise Http404 from None
    membership = TenantMembership.objects.filter(
        tenant_id=tenant_id,
        identity=request.user,
        status="ACTIVE",
        tenant__status="ACTIVE",
        role__in=["RECRUITER", "HIRING_MANAGER"],
    ).first()
    if membership is None or str(request.tenant_id) != str(tenant_id):
        raise Http404
    return membership, credential


def version(resource):
    if isinstance(resource, WorkflowRun):
        return digest(f"{resource.pk}:{resource.updated_at.isoformat()}:{resource.status}")
    raise ValueError("Expected interpretation workflow")


def search_version(search):
    return canonical_hash(
        {
            "criteria": _criteria(search),
            "snapshots": [
                str(pk) for pk in search.results.order_by("ordinal").values_list("id", flat=True)
            ],
        }
    )


def audit(item, membership, action):
    record_governance_event(
        membership=membership,
        action=f"SEARCH_HANDOFF_{action}",
        target_type="search_handoff",
        target_id=digest(str(item.pk)),
        handoff_type=item.kind,
        expiry_bucket="15_MINUTES",
    )


@transaction.atomic
def create(request, tenant_id, kind, *, internal_body=None, expires_at=None):
    membership, credential = authority(request, tenant_id)
    # Serialize retries and state changes within the same bound credential.
    type(credential).objects.select_for_update().get(pk=credential.pk)
    body = request.data if internal_body is None else internal_body
    key = request.headers.get("Idempotency-Key", "")
    if not 16 <= len(key) <= 200:
        raise ValidationError({"Idempotency-Key": "A retry key is required."})
    allowed = (
        {"workflow_id", "criteria", "search_id"}
        if kind == "criteria-review"
        else (
            {"search_id", "candidate_ids"}
            if kind == "comparison-selection"
            else {"search_id", "criteria_token", "page"}
        )
    )
    if not isinstance(body, dict) or set(body) - allowed:
        raise ValidationError("Unsupported handoff fields.")
    workflow = search = None
    payload: dict[str, Any]
    try:
        if kind == "criteria-review":
            if "search_id" in body:
                if set(body) != {"search_id"}:
                    raise ValidationError("Reopen accepts only the source search identifier.")
                from modules.ai.intent_schema import SearchIntent
                from modules.ai.search_graph import persist_checkpoint

                source = SearchDefinition.objects.get(
                    pk=str(body["search_id"]), tenant_id=tenant_id, actor=request.user
                )
                if source.expires_at <= timezone.now() and not hasattr(source, "saved"):
                    raise Http404
                validate_search_context(source.criteria_context, membership)
                existing = SearchWorkflowHandoff.objects.filter(
                    credential=credential, retry_hash=digest(f"{tenant_id}:{kind}:{key}")
                ).first()
                if existing is not None:
                    workflow = existing.workflow
                else:
                    workflow = persist_checkpoint(
                        SearchIntent(
                            criteria=SearchCriteriaInput.model_validate(_criteria(source)),
                            requires_review=True,
                            ambiguities=[],
                            ai_status="NOT_NEEDED",
                        ),
                        actor=request.user,
                        tenant_id=tenant_id,
                        prompt="",
                    )
                if workflow is None:
                    raise Http404
                body = {"workflow_id": str(workflow.pk), "criteria": _criteria(source)}
            workflow = WorkflowRun.objects.get(
                pk=str(body.get("workflow_id", "")),
                tenant_id=tenant_id,
                actor=request.user,
                workflow_type="SEARCH_INTERPRETATION",
                status="AWAITING_REVIEW",
                expires_at__gt=timezone.now(),
            )
            model = SearchCriteriaInput.model_validate(body.get("criteria"))
            checkpoint = json.loads(decrypt(bytes(workflow.checkpoint_ciphertext)))
            if not constant_time_compare(
                digest(model.model_dump_json(exclude={"cursor"})), checkpoint["criteria_hash"]
            ):
                raise Http404
            payload = {
                "schema_version": 1,
                "criteria": model.model_dump(mode="json", exclude_none=True),
            }
            validate_search_context(payload["criteria"]["context"], membership)
            resource_version = version(workflow)
        else:
            search = SearchDefinition.objects.get(
                pk=str(body.get("search_id", "")),
                tenant_id=tenant_id,
                actor=request.user,
                expires_at__gt=timezone.now(),
            )
            validate_search_context(search.criteria_context, membership)
            payload = {"schema_version": 1, "search_id": str(search.pk)}
            if kind == "search-results":
                page = body.get("page", 1)
                if type(page) is not int or not 1 <= page <= max(
                    1, (search.results.count() + search.result_limit - 1) // search.result_limit
                ):
                    raise ValidationError("Result page is unavailable.")
                payload["page"] = page
            if kind == "comparison-selection":
                payload["candidate_ids"] = selection_ids(
                    body.get("candidate_ids"), search, membership
                )
            resource_version = search_version(search)
    except (
        WorkflowRun.DoesNotExist,
        SearchDefinition.DoesNotExist,
        PermissionDenied,
        DjangoValidationError,
        CryptoError,
        KeyError,
    ):
        raise Http404 from None
    request_hash = canonical_hash(body)
    retry_hash = digest(f"{tenant_id}:{kind}:{key}")
    item = (
        SearchWorkflowHandoff.objects.select_for_update()
        .filter(credential=credential, retry_hash=retry_hash)
        .first()
    )
    token = secrets.token_urlsafe(32)
    fresh = item is None
    if item is not None:
        if (
            item.request_hash != request_hash
            or item.state != "ACTIVE"
            or item.expires_at <= timezone.now()
        ):
            raise Http404
        # A retry rotates the bearer, keeping exactly one record. Raw tokens are
        # deliberately not cached in the generic idempotency response table.
        item.token_hash = digest(token)
        item.save(update_fields=["token_hash"])
    else:
        item = SearchWorkflowHandoff.objects.create(
            tenant_id=tenant_id,
            actor=request.user,
            credential=credential,
            kind=kind,
            token_hash=digest(token),
            retry_hash=retry_hash,
            request_hash=request_hash,
            payload_ciphertext=encrypt(json.dumps(payload)),
            workflow=workflow,
            search=search,
            resource_version=resource_version,
            expires_at=min(timezone.now() + timedelta(minutes=15), expires_at)
            if expires_at is not None
            else timezone.now() + timedelta(minutes=15),
        )
        audit(item, membership, "CREATED")
    if fresh and kind == "search-results" and body.get("criteria_token"):
        assert search is not None
        previous, previous_payload, _ = restore(
            request, tenant_id, "criteria-review", body["criteria_token"], lock=True
        )
        if criteria_identity(previous_payload["criteria"]) != criteria_identity(_criteria(search)):
            raise Http404
        previous.state = "COMPLETED"
        previous.version += 1
        previous.save(update_fields=["state", "version"])
        previous.workflow.status = "COMPLETED"
        previous.workflow.save(update_fields=["status", "updated_at"])
        audit(previous, membership, "COMPLETED")
    return {
        "token": token,
        "expires_at": item.expires_at.isoformat(),
        "version": item.version,
        "kind": kind,
    }, fresh


def restore(request, tenant_id, kind, token=None, *, lock=False):
    membership, credential = authority(request, tenant_id)
    token = token if token is not None else request.headers.get("X-Workflow-Handoff", "")
    if not isinstance(token, str) or re.fullmatch(r"[A-Za-z0-9_-]{43}", token) is None:
        raise Http404
    records = SearchWorkflowHandoff.objects.all()
    if lock:
        records = records.select_for_update()
    item = records.filter(
        token_hash=digest(token),
        tenant_id=tenant_id,
        actor=request.user,
        credential=credential,
        kind=kind,
        state="ACTIVE",
        expires_at__gt=timezone.now(),
    ).first()
    if item is None:
        raise Http404
    resource: Any
    try:
        if kind == "criteria-review":
            resource = WorkflowRun.objects.get(
                pk=str(item.workflow_id),
                actor=request.user,
                tenant_id=tenant_id,
                status="AWAITING_REVIEW",
                workflow_type="SEARCH_INTERPRETATION",
                expires_at__gt=timezone.now(),
            )
            current_version = version(resource)
        else:
            resource = SearchDefinition.objects.get(
                pk=str(item.search_id),
                actor=request.user,
                tenant_id=tenant_id,
                expires_at__gt=timezone.now(),
            )
            current_version = search_version(resource)
        if not constant_time_compare(current_version, item.resource_version):
            raise Http404
        payload = json.loads(decrypt(bytes(item.payload_ciphertext)))
        if payload.get("schema_version") != 1:
            raise Http404
        if kind == "criteria-review":
            if set(payload) != {"schema_version", "criteria"}:
                raise Http404
            payload["criteria"] = SearchCriteriaInput.model_validate(
                payload["criteria"]
            ).model_dump(mode="json", exclude_none=True)
        elif kind == "comparison-selection":
            if set(payload) != {"schema_version", "search_id", "candidate_ids"} or payload[
                "search_id"
            ] != str(resource.pk):
                raise Http404
            selection_ids(payload["candidate_ids"], resource, membership)
        elif set(payload) != {"schema_version", "search_id", "page"} or payload["search_id"] != str(
            resource.pk
        ):
            raise Http404
        elif type(payload["page"]) is not int or not 1 <= payload["page"] <= max(
            1, (resource.results.count() + resource.result_limit - 1) // resource.result_limit
        ):
            raise Http404
        context = (
            payload["criteria"]["context"]
            if kind == "criteria-review"
            else resource.criteria_context
        )
        validate_search_context(context, membership)
    except (
        WorkflowRun.DoesNotExist,
        SearchDefinition.DoesNotExist,
        PermissionDenied,
        ValueError,
        KeyError,
        TypeError,
        CryptoError,
    ):
        raise Http404 from None
    return item, payload, membership


def metadata(item, payload, membership):
    output = {
        "schema_version": 1,
        "version": item.version,
        "etag": strong_etag(item.pk, item.version),
        "kind": item.kind,
    }
    if item.kind == "criteria-review":
        from .criteria_views import _estimate, _group_impacts

        output.update(
            criteria=payload["criteria"],
            workflow_id=str(item.workflow_id),
            workflow_version=item.resource_version,
            estimated_count=_estimate(membership, payload["criteria"]),
            group_impacts=_group_impacts(membership, payload["criteria"]),
        )
    else:
        output.update(search_id=str(item.search_id), result_context_version=item.resource_version)
        if item.kind == "search-results":
            output["page"] = payload["page"]
            output["criteria"] = _criteria(item.search)
        if item.kind == "comparison-selection":
            output.update(
                candidate_ids=payload["candidate_ids"],
                return_path=f"/tenants/{item.tenant_id}/recruiter/search/",
            )
    return output


@transaction.atomic
def revise(request, tenant_id, kind):
    item, payload, membership = restore(request, tenant_id, kind, lock=True)
    require_if_match(request.headers.get("If-Match"), item, {})
    if kind == "comparison-selection":
        if not isinstance(request.data, dict) or set(request.data) != {"candidate_ids"}:
            raise ValidationError("Only ordered candidate selection may be revised.")
        payload["candidate_ids"] = selection_ids(
            request.data["candidate_ids"], item.search, membership
        )
        item.payload_ciphertext = encrypt(json.dumps(payload))
        item.version += 1
        item.save(update_fields=["payload_ciphertext", "version", "updated_at"])
        audit(item, membership, "REVISED")
        return metadata(item, payload, membership)
    if set(request.data) != {"criteria"} or kind != "criteria-review":
        raise ValidationError("Only review criteria may be revised.")
    model = SearchCriteriaInput.model_validate(request.data["criteria"])
    criteria = model.model_dump(mode="json", exclude_none=True)
    if criteria["context"] != payload["criteria"]["context"]:
        raise ValidationError("The authorized context cannot change during review.")
    validate_search_context(criteria["context"], membership)
    payload["criteria"] = criteria
    item.payload_ciphertext = encrypt(json.dumps(payload))
    item.version += 1
    item.save(update_fields=["payload_ciphertext", "version"])
    audit(item, membership, "REVISED")
    return metadata(item, payload, membership)


def selection_ids(values, search, membership):
    """Selection is not authority: reuse current comparison context and field checks."""
    import uuid

    from modules.recruiting.comparison import _current_field_scope, _resolve_context

    from .eligibility import eligible_profiles
    from .query import search_authorization_context

    if not isinstance(values, list) or len(values) > 10:
        raise ValidationError("Select at most ten unique candidates.")
    try:
        ordered = [str(uuid.UUID(value)) for value in values if isinstance(value, str)]
    except ValueError:
        raise ValidationError("Invalid selection.") from None
    if len(ordered) != len(values) or len(set(ordered)) != len(ordered):
        raise ValidationError("Select at most ten unique candidates.")
    context = _resolve_context(membership=membership, context_type="SEARCH", context_id=search.pk)
    if not set(ordered) <= set(context.snapshots):
        raise Http404
    with search_authorization_context(context.eligibility_context):
        allowed = {
            str(profile.pk)
            for profile in eligible_profiles(membership, context.eligibility_context)
            .filter(pk__in=ordered)
            .prefetch_related("visibility_rules__consent_record")
            if _current_field_scope(profile, membership.tenant_id)
        }
    if not set(ordered) <= allowed:
        raise Http404
    return ordered
