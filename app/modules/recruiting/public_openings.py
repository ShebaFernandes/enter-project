"""FM3 public publication boundary. No public read ever joins the source table."""

from contextlib import contextmanager

from django.core.exceptions import PermissionDenied
from django.db import connection, transaction
from django.db.models import Q
from django.utils import timezone

from modules.tenancy.audit import record_governance_event
from modules.tenancy.models import TenantMembership
from modules.tenancy.policy import authorize_opening

from .models import Opening, OpeningPublicationLink, PublicOpeningProjection


@contextmanager
def public_reader():
    """Use real least-privilege credentials even on a superuser development connection."""
    if connection.vendor != "postgresql":
        raise PermissionDenied("Public roles unavailable")
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("SELECT current_user")
        previous = cursor.fetchone()[0]
        cursor.execute("SET LOCAL ROLE enter_public_openings_reader")
        try:
            yield
        finally:
            if not connection.needs_rollback:
                cursor.execute(f"SET LOCAL ROLE {connection.ops.quote_name(previous)}")


def available_publications():
    now = timezone.now()
    return PublicOpeningProjection.objects.filter(active=True, published_at__lte=now).filter(
        Q(closes_at__isnull=True) | Q(closes_at__gt=now)
    )


def public_data(item: PublicOpeningProjection) -> dict:
    return {
        "id": str(item.id),
        "title": item.title,
        "description": item.description,
        "location": item.location,
        "work_mode": item.work_mode,
        "employment_type": item.employment_type,
        "published_at": item.published_at,
        "closes_at": item.closes_at,
        "application_url": f"/roles/{item.id}/",
    }


@transaction.atomic
def application_publication_link(public_id) -> OpeningPublicationLink:
    """Internal resolution after candidate ownership and live public eligibility checks.

    An exact transaction-local public identifier, not a tenant supplied by the
    browser, scopes the private link read. The public reader has no link privileges.
    """
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_setting('app.public_opening_id', true)")
        previous = cursor.fetchone()[0] or ""
        cursor.execute("SELECT set_config('app.public_opening_id', %s, true)", [str(public_id)])
        try:
            return OpeningPublicationLink.objects.get(public_id=public_id)
        finally:
            cursor.execute("SELECT set_config('app.public_opening_id', %s, true)", [previous])


@transaction.atomic
def synchronize_publication(*, opening: Opening, membership) -> None:
    """Called only inside the authorized source write, never from a public request."""
    membership = (
        TenantMembership.objects.select_for_update()
        .filter(
            pk=membership.pk,
            tenant_id=opening.tenant_id,
            status=TenantMembership.Status.ACTIVE,
            tenant__status="ACTIVE",
        )
        .first()
    )
    if membership is None:
        raise PermissionDenied("Publication unavailable")
    opening = Opening.objects.select_for_update().get(pk=opening.pk, tenant_id=membership.tenant_id)
    authorize_opening(membership, opening, "opening.write")
    if opening.state != Opening.State.OPEN:
        record_governance_event(
            membership=membership,
            action="OPENING_PUBLICATION_WITHDRAWN",
            target_type="opening",
            target_id=opening.id,
        )
        return
    link, _ = OpeningPublicationLink.objects.get_or_create(
        opening=opening, defaults={"tenant_id": opening.tenant_id}
    )
    if link.tenant_id != opening.tenant_id:
        raise PermissionDenied("Publication unavailable")
    location = opening.location.get("display", opening.location.get("city", ""))
    # Never serialize the source JSON wholesale: it can contain private metadata.
    if not isinstance(location, str):
        location = ""
    PublicOpeningProjection.objects.update_or_create(
        id=link.public_id,
        defaults={
            "title": opening.title,
            "description": opening.description,
            "location": location[:300],
            "work_mode": opening.work_mode,
            "employment_type": opening.employment_type,
            "published_at": timezone.now(),
            "active": True,
        },
    )
    record_governance_event(
        membership=membership,
        action="OPENING_PUBLISHED",
        target_type="opening",
        target_id=opening.id,
        changed_fields=["public_role_essentials"],
    )
