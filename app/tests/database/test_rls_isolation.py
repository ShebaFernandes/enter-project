import uuid
from datetime import timedelta
from typing import cast

import pytest
from django.core.exceptions import PermissionDenied
from django.db import connection, transaction
from django.utils import timezone

from modules.tenancy.context import tenant_context
from modules.tenancy.models import AccessGrant, BusinessUnit, Tenant
from modules.tenancy.policy import AuthorizationRequest, authorize
from modules.tenancy.rls import tenant_transaction
from tests.factories import AccessGrantFactory


def test_missing_tenant_context_fails_closed():
    token = tenant_context.set(None)
    try:
        with pytest.raises(PermissionDenied), tenant_transaction():
            pass
    finally:
        tenant_context.reset(token)


@pytest.mark.postgres
@pytest.mark.django_db(transaction=True)
def test_postgres_rls_uses_transaction_local_context(tenant):
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL required")
    token = tenant_context.set(tenant.id)
    try:
        with tenant_transaction(), connection.cursor() as cursor:
            cursor.execute("SELECT current_setting('app.tenant_id', true)")
            assert cursor.fetchone()[0] == str(tenant.id)
    finally:
        tenant_context.reset(token)


@pytest.mark.postgres
@pytest.mark.django_db(transaction=True)
def test_postgres_rls_denies_missing_wrong_and_cross_tenant_joins(identity, tenant):
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL required")
    other = Tenant.objects.create(
        name="Other Synthetic Company",
        slug="other-rls-company",
        legal_boundary_reference="other-rls-contract",
        status=Tenant.Status.ACTIVE,
    )
    own_unit = BusinessUnit.objects.create(tenant=tenant, name="Own Unit", created_by=identity)
    BusinessUnit.objects.create(tenant=other, name="Other Unit", created_by=identity)
    role_name = f"rls_reader_{uuid.uuid4().hex[:12]}"
    quoted_role = connection.ops.quote_name(role_name)
    try:
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {quoted_role} NOLOGIN")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {quoted_role}")
            cursor.execute(
                f"GRANT SELECT ON tenancy_businessunit, recruiting_opening TO {quoted_role}"
            )
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(f"SET LOCAL ROLE {quoted_role}")
            cursor.execute("SELECT set_config('app.tenant_id', '', true)")
            cursor.execute("SELECT count(*) FROM tenancy_businessunit")
            assert cursor.fetchone()[0] == 0
            cursor.execute("SELECT set_config('app.tenant_id', %s, true)", [str(other.id)])
            cursor.execute(
                "SELECT count(*) FROM tenancy_businessunit WHERE id = %s", [str(own_unit.id)]
            )
            assert cursor.fetchone()[0] == 0
            cursor.execute("SELECT set_config('app.tenant_id', %s, true)", [str(tenant.id)])
            cursor.execute("SELECT array_agg(id) FROM tenancy_businessunit")
            assert cursor.fetchone()[0] == [own_unit.id]
            cursor.execute(
                """SELECT count(*) FROM tenancy_businessunit unit
                   JOIN recruiting_opening opening ON opening.business_unit_id = unit.id"""
            )
            assert cursor.fetchone()[0] == 0
            cursor.execute("RESET ROLE")
    finally:
        with connection.cursor() as cursor:
            cursor.execute(f"DROP OWNED BY {quoted_role}")
            cursor.execute(f"DROP ROLE IF EXISTS {quoted_role}")


@pytest.mark.postgres
@pytest.mark.django_db(transaction=True)
def test_all_foundation_tenant_tables_have_forced_rls():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL required")
    expected = {
        "tenancy_businessunit",
        "tenancy_tenantmembership",
        "tenancy_accessgrant",
        "tenancy_emergencyaccessrequest",
        "recruiting_opening",
        "recruiting_hiringteammember",
        "recruiting_application",
        "recruiting_applicationstatusevent",
        "recruiting_recruiterenteredcandidate",
        "communications_notification",
    }
    with connection.cursor() as cursor:
        cursor.execute(
            """SELECT relname FROM pg_class
               WHERE relname = ANY(%s) AND relrowsecurity AND relforcerowsecurity""",
            [list(expected)],
        )
        actual = {row[0] for row in cursor.fetchall()}
    assert actual == expected


@pytest.mark.django_db
def test_object_and_field_grants_cannot_bypass_tenant_isolation(identity, recruiter, tenant):
    candidate_id = str(uuid.uuid4())
    grant = cast(
        AccessGrant,
        AccessGrantFactory(
            tenant=tenant,
            grantee=identity,
            purpose_code="RECRUITING_REVIEW",
            field_scope=["skills"],
            object_scope={"ids": [candidate_id]},
            valid_from=timezone.now() - timedelta(minutes=1),
        ),
    )
    base = {
        "action": "candidate.field.read",
        "role": recruiter.role,
        "tenant_id": tenant.id,
        "object_tenant_id": tenant.id,
        "object_id": candidate_id,
        "purpose": "RECRUITING_REVIEW",
        "fields": frozenset({"skills"}),
        "consent_purposes": frozenset({"RECRUITING_REVIEW"}),
        "consent_fields": frozenset({"skills"}),
        "grant": grant,
        "actor": identity,
        "sensitive": True,
    }
    authorize(AuthorizationRequest(**base))
    with pytest.raises(PermissionDenied):
        authorize(AuthorizationRequest(**{**base, "tenant_id": uuid.uuid4()}))
    with pytest.raises(PermissionDenied):
        authorize(AuthorizationRequest(**{**base, "fields": frozenset({"email"})}))
