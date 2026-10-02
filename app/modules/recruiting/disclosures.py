from __future__ import annotations

from datetime import timedelta
from typing import cast

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from modules.candidate.models import CandidateContact, CandidateProfile, ConsentRecord
from modules.operations.concurrency import canonical_hash
from modules.operations.crypto import decrypt, encrypt
from modules.operations.outbox import enqueue
from modules.search.eligibility import eligible_profiles
from modules.tenancy.policy import AuthorizationRequest, authorize, authorize_opening

from .application_models import Application
from .audit import record_disclosure_histories, record_recruiting_event
from .candidate_work import authorize_application, authorize_candidate_work
from .work_models import CandidateWorkRecord, DisclosureRequest

DISCLOSABLE_FIELDS = frozenset(
    {
        "name",
        "profile_summary",
        "skills",
        "employment_history",
        "resume",
        "application_summary",
        "contact_email",
        "contact_whatsapp",
    }
)
PURPOSE_MINIMUM_FIELDS = {
    "CANDIDATE_CONTACT": frozenset({"name", "contact_email", "contact_whatsapp"}),
    "HIRING_TEAM_SHARE": frozenset(
        {"name", "profile_summary", "skills", "employment_history", "application_summary"}
    ),
}


def _context(*, membership, context_type: str, context_id):
    if context_type == "APPLICATION":
        application = (
            Application.objects.select_related("opening")
            .filter(pk=context_id, tenant_id=membership.tenant_id)
            .first()
        )
        if application is None:
            raise PermissionDenied("Disclosure unavailable")
        authorize_application(membership, application, "candidate.disclosure.preview")
        return application
    if context_type == "CANDIDATE_WORK":
        candidate_work = (
            CandidateWorkRecord.objects.select_related("opening", "originating_search")
            .filter(pk=context_id, tenant_id=membership.tenant_id)
            .first()
        )
        if candidate_work is None:
            raise PermissionDenied("Disclosure unavailable")
        authorize_candidate_work(membership, candidate_work, "candidate.disclosure.preview")
        return candidate_work
    raise ValidationError({"context_type": "Unsupported disclosure context."})


def _visible(*, membership, context) -> bool:
    if isinstance(context, Application):
        return context.state in {Application.State.SUBMITTED, Application.State.ACTIVE}
    profile = context.candidate_profile
    return (
        eligible_profiles(membership, context.originating_search.criteria_context)
        .filter(pk=profile.pk)
        .exists()
    )


def _current_consent(*, context, purpose: str) -> ConsentRecord:
    now = timezone.now()
    consents = ConsentRecord.objects.filter(
        profile_id=context.candidate_profile_id,
        purpose=purpose,
        withdrawn_at__isnull=True,
        expires_at__gt=now,
    ).order_by("-captured_at")
    for consent in consents:
        audience = consent.audience_scope
        tenant_matches = audience.get("tenant_id") == str(context.tenant_id) or str(
            context.tenant_id
        ) in audience.get("approved_tenant_ids", [])
        opening_id = getattr(context, "opening_id", None)
        opening_matches = not audience.get("opening_id") or audience.get("opening_id") == str(
            opening_id
        )
        if tenant_matches and opening_matches:
            return consent
    raise PermissionDenied("Disclosure unavailable")


def _destination_preview(destination: dict[str, object]) -> tuple[str, str, str]:
    destination_type = str(destination.get("type", "")).upper()
    identifier = str(destination.get("identifier", "")).strip()
    label = str(destination.get("label", "")).strip()
    if destination_type not in {"CANDIDATE_EMAIL", "CANDIDATE_WHATSAPP", "HIRING_TEAM"}:
        raise ValidationError({"destination": "Destination type is not supported."})
    if not identifier:
        raise ValidationError({"destination": "Destination identifier is required."})
    if destination_type == "HIRING_TEAM":
        preview = label or f"Hiring team {identifier}"
    elif "@" in identifier:
        local, domain = identifier.split("@", 1)
        preview = f"{local[:1]}***@{domain}"
    else:
        preview = f"***{identifier[-4:]}"
    return destination_type, identifier, preview


def _validate_destination(*, membership, context, destination_type: str, identifier: str) -> None:
    if destination_type == "HIRING_TEAM":
        if not context.opening_id or str(context.opening_id) != identifier:
            raise PermissionDenied("Disclosure unavailable")
        authorize_opening(membership, context.opening, "opening.read")
        return
    profile = CandidateProfile.objects.select_related("identity").get(
        pk=context.candidate_profile_id
    )
    if destination_type == "CANDIDATE_EMAIL":
        expected = decrypt(bytes(profile.identity.email_ciphertext))
    else:
        contact = CandidateContact.objects.filter(
            profile=profile,
            channel="WHATSAPP",
            verified_at__isnull=False,
        ).first()
        if contact is None:
            raise PermissionDenied("Disclosure unavailable")
        expected = decrypt(bytes(contact.value_ciphertext))
    if expected.casefold() != identifier.casefold():
        raise PermissionDenied("Disclosure unavailable")


def disclosure_data(disclosure: DisclosureRequest) -> dict[str, object]:
    return {
        "preview_id": str(disclosure.id),
        "preview_hash": disclosure.preview_hash,
        "destination": {
            "type": disclosure.destination_type,
            "label": disclosure.destination_preview,
        },
        "purpose": disclosure.purpose,
        "permitted_fields": disclosure.permitted_fields,
        "excluded_fields": disclosure.excluded_fields,
        "expires_at": disclosure.expires_at,
        "state": disclosure.state,
        "result_category": disclosure.result_category or None,
    }


def _authorize_fields(*, membership, context, consent, purpose: str, fields: set[str]) -> None:
    authorize(
        AuthorizationRequest(
            action="candidate.disclosure.preview",
            role=membership.role,
            tenant_id=membership.tenant_id,
            object_tenant_id=context.tenant_id,
            purpose=purpose,
            fields=frozenset(fields),
            object_id=str(context.id),
            consent_purposes=frozenset({consent.purpose}),
            consent_fields=frozenset(consent.field_scope),
            grant=_context_grant(membership, context, consent, purpose),
            actor=membership.identity,
            sensitive=True,
        )
    )


def _context_grant(membership, context, consent, purpose):
    """Build no synthetic grant: use a persisted matching purpose grant when one is required."""
    from modules.tenancy.models import AccessGrant

    return AccessGrant.objects.filter(
        tenant_id=context.tenant_id,
        grantee_id=membership.identity_id,
        purpose_code=purpose,
        status=AccessGrant.Status.ACTIVE,
        valid_from__lte=timezone.now(),
        expires_at__gt=timezone.now(),
    ).first()


@transaction.atomic
def preview_disclosure(
    *, membership, candidate_id, values: dict[str, object], request_key: str
) -> DisclosureRequest:
    context = _context(
        membership=membership,
        context_type=str(values["context_type"]),
        context_id=values["context_id"],
    )
    if str(context.candidate_profile_id) != str(candidate_id) or not _visible(
        membership=membership, context=context
    ):
        raise PermissionDenied("Disclosure unavailable")
    purpose = str(values["purpose"])
    if purpose not in PURPOSE_MINIMUM_FIELDS:
        raise ValidationError({"purpose": "Disclosure purpose is not supported."})
    requested = {str(value) for value in values["requested_fields"]}
    if not requested or not requested.issubset(DISCLOSABLE_FIELDS):
        raise ValidationError({"requested_fields": "Requested fields are invalid."})
    permitted_for_purpose = PURPOSE_MINIMUM_FIELDS[purpose]
    consent = _current_consent(context=context, purpose=purpose)
    permitted = requested & permitted_for_purpose & set(consent.field_scope)
    if not permitted:
        raise PermissionDenied("Disclosure unavailable")
    _authorize_fields(
        membership=membership,
        context=context,
        consent=consent,
        purpose=purpose,
        fields=permitted,
    )
    destination_type, identifier, destination_preview = _destination_preview(
        cast(dict[str, object], values["destination"])
    )
    _validate_destination(
        membership=membership,
        context=context,
        destination_type=destination_type,
        identifier=identifier,
    )
    material = {
        "candidate_id": str(candidate_id),
        "context_type": str(values["context_type"]),
        "context_id": str(context.id),
        "purpose": purpose,
        "destination_type": destination_type,
        "destination_identifier": identifier,
        "permitted_fields": sorted(permitted),
        "consent_id": str(consent.id),
    }
    disclosure = DisclosureRequest(
        tenant_id=context.tenant_id,
        candidate_profile_id=candidate_id,
        application=context if isinstance(context, Application) else None,
        candidate_work=context if isinstance(context, CandidateWorkRecord) else None,
        purpose=purpose,
        destination_type=destination_type,
        destination_identifier_ciphertext=encrypt(identifier),
        destination_preview=destination_preview,
        requested_fields=sorted(requested),
        permitted_fields=sorted(permitted),
        excluded_fields=sorted(requested - permitted),
        consent_record=consent,
        preview_hash=canonical_hash(material),
        expires_at=timezone.now() + timedelta(minutes=10),
        idempotency_key=f"disclosure-preview:{request_key}",
    )
    disclosure.full_clean()
    disclosure.save()
    record_recruiting_event(
        actor=membership.identity,
        tenant_id=disclosure.tenant_id,
        action="CANDIDATE_DISCLOSURE_PREVIEWED",
        target_type="disclosure_request",
        target_id=disclosure.id,
        permitted_fields=disclosure.permitted_fields,
        excluded_fields=disclosure.excluded_fields,
        destination_type=destination_type,
    )
    return disclosure


@transaction.atomic
def confirm_disclosure(
    *, membership, candidate_id, preview_id, preview_hash: str, request_key: str
) -> DisclosureRequest:
    disclosure = (
        DisclosureRequest.objects.select_for_update(of=("self",))
        .select_related(
            "application__opening",
            "candidate_work__opening",
            "candidate_work__originating_search",
            "candidate_profile",
            "consent_record",
        )
        .filter(pk=preview_id, tenant_id=membership.tenant_id)
        .first()
    )
    if disclosure is None or str(disclosure.candidate_profile_id) != str(candidate_id):
        raise PermissionDenied("Disclosure unavailable")
    if (
        disclosure.preview_hash != preview_hash
        or disclosure.state != DisclosureRequest.State.PREVIEWED
        or disclosure.expires_at <= timezone.now()
    ):
        raise ValidationError({"preview_id": "Disclosure preview is stale or invalid."})
    context = disclosure.application or disclosure.candidate_work
    if context is None:
        raise PermissionDenied("Disclosure unavailable")
    if isinstance(context, Application):
        authorize_application(membership, context, "candidate.disclosure.confirm")
    elif isinstance(context, CandidateWorkRecord):
        authorize_candidate_work(membership, context, "candidate.disclosure.confirm")
    else:
        raise PermissionDenied("Disclosure unavailable")
    if not _visible(membership=membership, context=context):
        raise PermissionDenied("Disclosure unavailable")
    consent = _current_consent(context=context, purpose=disclosure.purpose)
    if consent.id != disclosure.consent_record_id:
        raise PermissionDenied("Disclosure unavailable")
    fields = set(disclosure.permitted_fields)
    if not fields.issubset(set(consent.field_scope)):
        raise PermissionDenied("Disclosure unavailable")
    _authorize_fields(
        membership=membership,
        context=context,
        consent=consent,
        purpose=disclosure.purpose,
        fields=fields,
    )
    disclosure.confirmed_by = membership.identity
    disclosure.confirmed_at = timezone.now()
    disclosure.state = DisclosureRequest.State.PENDING
    disclosure.result_category = "QUEUED"
    disclosure.idempotency_key = f"disclosure-confirm:{request_key}"
    disclosure.save(
        update_fields=(
            "confirmed_by",
            "confirmed_at",
            "state",
            "result_category",
            "idempotency_key",
        )
    )
    enqueue(
        aggregate_type="disclosure_request",
        aggregate_id=disclosure.id,
        aggregate_version=1,
        event_type="candidate_disclosure.confirmed.v1",
        payload={"disclosure_id": str(disclosure.id)},
        idempotency_key=f"candidate-disclosure-event:{request_key}",
        tenant_id=disclosure.tenant_id,
        actor_id=membership.identity_id,
    )
    record_disclosure_histories(
        actor=membership.identity,
        disclosure=disclosure,
        outcome="ALLOWED",
        result_category="QUEUED",
    )
    return disclosure


@transaction.atomic
def record_disclosure_result(*, disclosure_id, succeeded: bool, result_category: str):
    disclosure = DisclosureRequest.objects.select_for_update().get(pk=disclosure_id)
    if disclosure.state not in {DisclosureRequest.State.PENDING, DisclosureRequest.State.FAILED}:
        raise ValidationError({"state": "Disclosure is not awaiting delivery."})
    disclosure.state = (
        DisclosureRequest.State.SUCCEEDED if succeeded else DisclosureRequest.State.FAILED
    )
    disclosure.result_category = result_category
    disclosure.save(update_fields=("state", "result_category"))
    record_disclosure_histories(
        actor=None,
        disclosure=disclosure,
        outcome="ALLOWED" if succeeded else "FAILED",
        result_category=result_category,
    )
    return disclosure
