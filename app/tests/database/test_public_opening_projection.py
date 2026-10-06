"""FM3: exercise public access using the actual restricted database role."""

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, connection, transaction
from django.utils import timezone

from modules.recruiting.models import PublicOpeningProjection
from modules.recruiting.openings import update_opening
from modules.recruiting.public_openings import public_reader
from modules.tenancy.context import tenant_context
from modules.tenancy.rls import tenant_transaction

pytestmark = [pytest.mark.django_db, pytest.mark.postgres]


def publish(opening, recruiter):
    # Job publication is an admin action in production. Older contract tests
    # pass the shared recruiter fixture; resolve an admin test membership for
    # that same identity so the fixture still models an approved admin flow.
    if recruiter.role == "RECRUITER":
        from modules.tenancy.models import TenantMembership

        TenantMembership.objects.filter(pk=recruiter.pk).update(
            role=TenantMembership.Role.TENANT_ADMIN
        )
        recruiter.role = TenantMembership.Role.TENANT_ADMIN
    token = tenant_context.set(recruiter.tenant_id)
    try:
        with tenant_transaction():
            from modules.recruiting.public_openings import (
                publication_preview,
                synchronize_publication,
            )

            opening.refresh_from_db()
            if opening.state != "OPEN":
                opening = update_opening(
                    opening=opening, membership=recruiter, changes={"state": "OPEN"}
                )
            preview = publication_preview(opening)
            result = synchronize_publication(
                opening=opening,
                membership=recruiter,
                confirmed=True,
                if_match=preview["source_etag"],
                preview_digest=preview["preview_digest"],
            )
            opening.refresh_from_db()
            return result
    finally:
        tenant_context.reset(token)


def test_projection_is_explicit_publication_only(opening_factory, tenant, recruiter):
    draft = opening_factory(tenant=tenant, state="DRAFT")
    assert not PublicOpeningProjection.objects.exists()
    publish(draft, recruiter)
    projection = PublicOpeningProjection.objects.get()
    assert projection.id != draft.id
    with public_reader():
        assert list(PublicOpeningProjection.objects.values_list("id", flat=True)) == [projection.id]
        with connection.cursor() as cursor:
            cursor.execute("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname=current_user")
            assert cursor.fetchone() == (False, False)
            cursor.execute(
                "SELECT pg_get_userbyid(relowner) <> current_user FROM pg_class "
                "WHERE relname='recruiting_publicopeningprojection'"
            )
            assert cursor.fetchone() == (True,)
        for sql in (
            "SELECT * FROM recruiting_opening",
            "SELECT * FROM recruiting_openingpublicationlink",
            "DELETE FROM recruiting_publicopeningprojection",
            "UPDATE recruiting_publicopeningprojection SET title='unauthorized'",
            "INSERT INTO recruiting_publicopeningprojection (id) VALUES (gen_random_uuid())",
        ):
            with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
                cursor.execute(sql)


def test_expired_and_unpublished_are_hidden(opening_factory, tenant, tenant_admin):
    opening = opening_factory(tenant=tenant, state="DRAFT")
    publish(opening, tenant_admin)
    projection = PublicOpeningProjection.objects.get()
    projection.closes_at = timezone.now() - timedelta(seconds=1)
    projection.save()
    with public_reader():
        assert not PublicOpeningProjection.objects.exists()
    projection.closes_at = None
    projection.active = False
    projection.save()
    with public_reader():
        assert not PublicOpeningProjection.objects.exists()


def test_source_change_invalidates_publication_even_without_service(
    opening_factory, tenant, tenant_admin
):
    opening = opening_factory(tenant=tenant, state="DRAFT")
    publish(opening, tenant_admin)
    type(opening).objects.filter(pk=opening.pk).update(state="CLOSED")
    with public_reader():
        assert not PublicOpeningProjection.objects.exists()


def test_failed_publication_does_not_commit_source_or_projection(
    opening_factory, tenant, tenant_admin
):
    opening = opening_factory(tenant=tenant, state="DRAFT")
    with (
        patch(
            "modules.recruiting.public_openings.synchronize_publication",
            side_effect=RuntimeError("synthetic failure"),
        ),
        pytest.raises(RuntimeError),
    ):
        publish(opening, tenant_admin)
    opening.refresh_from_db()
    assert opening.state == "DRAFT"
    assert not PublicOpeningProjection.objects.exists()


def test_updates_withdrawals_and_deletion(opening_factory, tenant, tenant_admin):
    from modules.audit.models import AuditEvent

    opening = opening_factory(tenant=tenant, state="DRAFT")
    publish(opening, tenant_admin)
    token = tenant_context.set(tenant.id)
    try:
        with tenant_transaction():
            update_opening(
                opening=opening,
                membership=tenant_admin,
                changes={"title": "Updated role"},
            )
            with public_reader():
                assert not PublicOpeningProjection.objects.exists()
            publish(opening, tenant_admin)
            assert PublicOpeningProjection.objects.get().title == "Updated role"
            update_opening(opening=opening, membership=tenant_admin, changes={"state": "PAUSED"})
            with public_reader():
                assert not PublicOpeningProjection.objects.exists()
            update_opening(opening=opening, membership=tenant_admin, changes={"state": "OPEN"})
            with public_reader():
                assert not PublicOpeningProjection.objects.exists()
            publish(opening, tenant_admin)
            opening.delete()
            with public_reader():
                assert not PublicOpeningProjection.objects.exists()
    finally:
        tenant_context.reset(token)
    assert AuditEvent.objects.filter(action="OPENING_PUBLISHED").exists()
    assert AuditEvent.objects.filter(action="OPENING_PUBLICATION_WITHDRAWN").exists()


def test_private_open_edit_is_not_publication(opening_factory, tenant, recruiter, tenant_admin):
    opening = opening_factory(tenant=tenant)
    update_opening(opening=opening, membership=tenant_admin, changes={"title": "Private edit"})
    assert not PublicOpeningProjection.objects.exists()


def test_cross_tenant_and_revoked_membership_cannot_publish(opening_factory, tenant, recruiter):
    from modules.recruiting.public_openings import synchronize_publication
    from tests.factories import TenantFactory

    other = opening_factory(tenant=TenantFactory(), state="DRAFT")
    with pytest.raises(PermissionDenied):
        publish(other, recruiter)
    own = opening_factory(tenant=tenant)
    recruiter.status = "REVOKED"
    recruiter.save()
    with pytest.raises(PermissionDenied):
        synchronize_publication(opening=own, membership=recruiter)
    assert not PublicOpeningProjection.objects.exists()


def test_restricted_writer_cannot_change_other_tenant_publication(
    opening_factory, tenant, recruiter, tenant_admin
):
    import uuid

    opening = opening_factory(tenant=tenant, state="DRAFT")
    publish(opening, tenant_admin)
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("SET LOCAL ROLE enter_opening_publisher")
        cursor.execute("SELECT set_config('app.tenant_id', %s, true)", [str(uuid.uuid4())])
        cursor.execute("SELECT set_config('app.identity_id', '', true)")
        cursor.execute("UPDATE recruiting_publicopeningprojection SET title='not authorized'")
        assert cursor.rowcount == 0
        cursor.execute("SELECT count(*) FROM recruiting_openingpublicationlink")
        assert cursor.fetchone()[0] == 0
        cursor.execute("RESET ROLE")
    assert PublicOpeningProjection.objects.get().title == opening.title
    with connection.cursor() as cursor:
        cursor.execute("SELECT policyname FROM pg_policies WHERE tablename='recruiting_opening'")
        assert cursor.fetchall() == [("tenant_isolation",)]
        cursor.execute(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
            "WHERE relname='recruiting_opening'"
        )
        assert cursor.fetchone() == (True, True)
