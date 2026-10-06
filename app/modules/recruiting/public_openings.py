"""FM3 public publication boundary. No public read ever joins the source table."""

from contextlib import contextmanager
from uuid import UUID

from django.core.exceptions import PermissionDenied
from django.db import connection, transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac
from rest_framework.exceptions import ValidationError

from modules.operations.concurrency import StaleWrite, canonical_hash, require_if_match, strong_etag
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
        "company_name": item.company_name,
        "about_company": item.about_company,
        "role_summary": item.role_summary,
        "responsibilities": item.responsibilities,
        "requirements": item.requirements,
        "nice_to_have": item.nice_to_have,
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


def authorized_publication_opening(*, opening: Opening, membership):
    """Call inside an atomic transaction; revalidate before mutation AND replay."""
    if membership is None:
        raise PermissionDenied("Publication unavailable")
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
    return opening, membership


def _public_id(opening):
    link = OpeningPublicationLink.objects.filter(opening=opening).first()
    if link:
        return link.public_id
    # Stable without a GET-side write, and not reversible to an internal ID.
    return UUID(
        salted_hmac("opening-public-id", str(opening.id), algorithm="sha256").hexdigest()[:32]
    )


def _source_fields(opening):
    location = opening.location.get("display", opening.location.get("city", ""))
    # Never serialize the source JSON wholesale: it can contain private metadata.
    if not isinstance(location, str):
        location = ""
    return {
        "title": opening.title,
        "description": opening.description,
        "company_name": opening.company_name,
        "about_company": opening.about_company,
        "role_summary": opening.role_summary,
        "responsibilities": opening.responsibilities,
        "requirements": opening.requirements,
        "nice_to_have": opening.nice_to_have,
        "location": location[:300],
        "work_mode": opening.work_mode,
        "employment_type": opening.employment_type,
    }


def publication_preview(opening):
    public_id = _public_id(opening)
    projection = PublicOpeningProjection.objects.filter(pk=public_id).first()
    published = available_publications().filter(pk=public_id).exists()
    fields = {
        "id": str(public_id),
        **_source_fields(opening),
        # The publication timestamp is assigned on confirmation, not browser supplied.
        "published_at": None,
        "closes_at": projection.closes_at.isoformat()
        if projection and projection.closes_at
        else None,
        "application_url": f"/roles/{public_id}/",
    }
    digest = salted_hmac(
        "opening-publication-preview-v1",
        canonical_hash(
            {
                "tenant": str(opening.tenant_id),
                "opening": str(opening.id),
                "version": opening.version,
                "fields": fields,
                "projection_version": projection.version if projection else 0,
                "published": published,
            }
        ),
        algorithm="sha256",
    ).hexdigest()
    return {
        "internal_state": opening.state,
        "publication_state": "PUBLISHED" if published else "UNPUBLISHED",
        "public_fields": fields,
        "public_url": fields["application_url"] if published else None,
        "source_version": opening.version,
        "source_etag": strong_etag(opening.id, opening.version),
        "projection_version": projection.version if projection else 0,
        "preview_digest": digest,
    }


@transaction.atomic
def synchronize_publication(
    *,
    opening: Opening,
    membership,
    if_match=None,
    confirmed=False,
    preview_digest="",
    withdraw=False,
) -> dict:
    """The only publication writer: explicit confirmation, locked source and minimized audit."""
    opening, membership = authorized_publication_opening(opening=opening, membership=membership)
    require_if_match(if_match, opening, {})
    if confirmed is not True:
        raise ValidationError({"confirmed": "Explicit confirmation is required."})
    preview = publication_preview(opening)
    if not withdraw:
        if not isinstance(preview_digest, str) or not constant_time_compare(
            preview_digest, preview["preview_digest"]
        ):
            raise StaleWrite(
                current={}, attempted={}, object_id=opening.id, version=opening.version
            )
        if opening.state != Opening.State.OPEN or opening.business_unit.status != "ACTIVE":
            raise ValidationError({"opening": "Only an active OPEN opening may be published."})
        if (
            preview["public_fields"]["closes_at"]
            and timezone.datetime.fromisoformat(preview["public_fields"]["closes_at"])
            <= timezone.now()
        ):
            raise ValidationError({"opening": "Expired publication is unavailable."})
    public_id = UUID(preview["public_fields"]["id"])
    # Advancing the opening ETag serializes publication/withdrawal and source edits.
    # Its existing SECURITY INVOKER trigger invalidates the previous projection.
    opening.version += 1
    opening.save(update_fields=["version", "updated_at"])
    if withdraw:
        PublicOpeningProjection.objects.filter(pk=public_id).update(
            active=False, version=opening.version
        )
    else:
        link, _ = OpeningPublicationLink.objects.get_or_create(
            opening=opening, defaults={"tenant_id": opening.tenant_id, "public_id": public_id}
        )
        if link.tenant_id != opening.tenant_id:
            raise PermissionDenied("Publication unavailable")
        PublicOpeningProjection.objects.update_or_create(
            id=link.public_id,
            defaults={
                **_source_fields(opening),
                "published_at": timezone.now(),
                "active": True,
                "version": opening.version,
            },
        )
    record_governance_event(
        membership=membership,
        action="OPENING_PUBLICATION_WITHDRAWN" if withdraw else "OPENING_PUBLISHED",
        target_type="opening",
        target_id=opening.id,
        changed_fields=["public_role_essentials"],
    )
    return publication_preview(opening)
