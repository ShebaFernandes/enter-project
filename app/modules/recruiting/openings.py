from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction

from modules.tenancy.audit import record_governance_event
from modules.tenancy.models import BusinessUnit, TenantMembership
from modules.tenancy.policy import AuthorizationRequest, authorize, authorize_opening

from .models import HiringTeamMember, Opening, OpeningPublicationLink, PublicOpeningProjection


def _authorize_membership(membership: TenantMembership, action: str, tenant_id) -> None:
    authorize(
        AuthorizationRequest(
            action=action,
            role=membership.role,
            tenant_id=membership.tenant_id,
            object_tenant_id=tenant_id,
        )
    )


@transaction.atomic
def create_opening(
    *, membership: TenantMembership, business_unit_id, hiring_team_ids=(), **fields
) -> Opening:
    _authorize_membership(membership, "opening.write", membership.tenant_id)
    unit = BusinessUnit.objects.get(
        pk=business_unit_id, tenant_id=membership.tenant_id, status=BusinessUnit.Status.ACTIVE
    )
    unit_scope = {str(value) for value in membership.scope.get("business_unit_ids", [])}
    if unit_scope and str(unit.id) not in unit_scope:
        raise ValidationError({"business_unit_id": "Business unit is unavailable."})
    opening = Opening(
        tenant_id=membership.tenant_id, business_unit=unit, created_by=membership.identity, **fields
    )
    opening.full_clean()
    opening.save()
    _replace_hiring_team(opening, membership, hiring_team_ids)
    record_governance_event(
        membership=membership,
        action="OPENING_CREATE",
        target_type="opening",
        target_id=opening.id,
        changed_fields=["business_unit_id", "title", "location", "work_mode", "employment_type"],
    )
    return opening


@transaction.atomic
def update_opening(
    *, opening: Opening, membership: TenantMembership, changes: dict, hiring_team_ids=None
) -> Opening:
    authorize_opening(membership, opening, "opening.write")
    was_public = PublicOpeningProjection.objects.filter(
        id__in=OpeningPublicationLink.objects.filter(opening=opening).values("public_id"),
        active=True,
    ).exists()
    if "state" in changes and changes["state"] != opening.state:
        current_state = Opening.State(opening.state)
        target_state = Opening.State(changes["state"])
        transitions = {
            Opening.State.DRAFT: {Opening.State.OPEN, Opening.State.CLOSED},
            Opening.State.OPEN: {Opening.State.PAUSED, Opening.State.CLOSED},
            Opening.State.PAUSED: {Opening.State.OPEN, Opening.State.CLOSED},
            Opening.State.CLOSED: set(),
        }
        if target_state not in transitions[current_state]:
            raise ValidationError({"state": "Invalid opening lifecycle transition."})
    for key in {"title", "description", "state"} & changes.keys():
        setattr(opening, key, changes[key])
    opening.version += 1
    opening.full_clean()
    opening.save()
    if hiring_team_ids is not None:
        _replace_hiring_team(opening, membership, hiring_team_ids)
    from .public_openings import synchronize_publication

    # Editing a pre-existing private OPEN record is not an implicit publication.
    if was_public or "state" in changes:
        synchronize_publication(opening=opening, membership=membership)
    record_governance_event(
        membership=membership,
        action="OPENING_UPDATE",
        target_type="opening",
        target_id=opening.id,
        changed_fields=sorted(
            set(changes) | ({"hiring_team_ids"} if hiring_team_ids is not None else set())
        ),
    )
    return opening


def _replace_hiring_team(opening: Opening, actor: TenantMembership, membership_ids) -> None:
    members = list(
        TenantMembership.objects.filter(
            id__in=membership_ids,
            tenant_id=opening.tenant_id,
            status=TenantMembership.Status.ACTIVE,
        )
    )
    if len(members) != len(set(membership_ids)):
        raise ValidationError(
            {"hiring_team_ids": "Every member must be active in the same tenant."}
        )
    if any(
        item.role not in {TenantMembership.Role.RECRUITER, TenantMembership.Role.HIRING_MANAGER}
        for item in members
    ):
        raise ValidationError({"hiring_team_ids": "Hiring team members must have a hiring role."})
    opening.hiring_team.all().delete()
    HiringTeamMember.objects.bulk_create(
        [
            HiringTeamMember(opening=opening, membership=item, assigned_by=actor.identity)
            for item in members
        ]
    )
